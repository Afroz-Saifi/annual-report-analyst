import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import AgentPipeline, build_agent
from app.db.models import Chunk, Report
from app.qa.baseline import DraftAnswer, answer_question
from app.retrieval.retriever import HybridRetriever
from app.retrieval.types import RetrievedChunk
from app.schemas.ask import AskResponse
from tests.fakes import AxisEmbeddings, FakeAnswerGenerator, FakeQueryRewriter, axis_vector
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio

NOT_FOUND = DraftAnswer(answer="The sources do not say.", citations=[], found=False)


def answer_when_dividend_page_is_shown(sources: list[RetrievedChunk]) -> DraftAnswer:
    for number, source in enumerate(sources, start=1):
        if "dividend" in source.content:
            return DraftAnswer(
                answer=f"A final dividend was recommended [{number}].",
                citations=[number],
                found=True,
            )
    return NOT_FOUND


def pipeline(
    generator: FakeAnswerGenerator, rewriter: FakeQueryRewriter, max_rewrites: int = 2
) -> AgentPipeline:
    # The query vector always points at page 1, so only keyword matches reach other pages.
    retriever = HybridRetriever(AxisEmbeddings(query_axis=0))
    return AgentPipeline(build_agent(retriever, generator, rewriter, max_rewrites))


async def ask(
    agent: AgentPipeline, session: AsyncSession, question: str
) -> tuple[AskResponse, list[RetrievedChunk]]:
    final = await answer_question(agent, session, question, top_k=1)
    return final.response, final.sources


async def test_an_answer_found_on_the_first_search_needs_no_rewrite(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(
        DraftAnswer(answer="Revenue grew [1].", citations=[1], found=True)
    )
    rewriter = FakeQueryRewriter()

    response, sources = await ask(pipeline(generator, rewriter), db_session, "revenue")

    assert response.answer == "Revenue grew [1]."
    assert [step.step for step in response.steps] == ["scope", "retrieve", "answer", "verify"]
    assert [citation.page_number for citation in response.citations] == [1]
    assert response.verified is True
    assert rewriter.calls == []
    assert [source.page_number for source in sources] == [1]


async def test_a_missed_answer_is_found_after_rewriting_the_query(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(answer_when_dividend_page_is_shown)
    rewriter = FakeQueryRewriter(["final dividend recommended"])

    response, sources = await ask(
        pipeline(generator, rewriter), db_session, "payout to shareholders"
    )

    assert [step.step for step in response.steps] == [
        "scope",
        "retrieve",
        "answer",
        "rewrite",
        "retrieve",
        "answer",
        "verify",
    ]
    assert [citation.page_number for citation in response.citations] == [3]
    assert rewriter.calls == [["payout to shareholders"]]
    assert [source.page_number for source in sources] == [3]


async def test_the_agent_stops_rewriting_at_the_limit(db_session: AsyncSession) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(NOT_FOUND)
    rewriter = FakeQueryRewriter(["first retry"], ["second retry"], ["never used"])

    response, _ = await ask(
        pipeline(generator, rewriter, max_rewrites=2), db_session, "football world cup"
    )

    assert response.answer == "The sources do not say."
    assert response.citations == []
    assert response.verified is None
    assert len(generator.calls) == 3
    assert rewriter.calls == [
        ["football world cup"],
        ["football world cup", "first retry"],
    ]


async def test_a_figure_missing_from_the_cited_source_is_flagged(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(
        DraftAnswer(answer="Revenue grew 9.6% [1].", citations=[1], found=True)
    )

    response, _ = await ask(
        pipeline(generator, FakeQueryRewriter(), max_rewrites=0), db_session, "revenue"
    )

    assert response.verified is False
    assert response.unverified_figures == ["9.6"]
    assert response.steps[-1].detail == "Not found in the cited sources: 9.6"


async def test_an_unverified_figure_sends_the_agent_back_to_search(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    def guess_then_read(sources: list[RetrievedChunk]) -> DraftAnswer:
        if "dividend" in sources[0].content:
            return DraftAnswer(answer="A final dividend [1].", citations=[1], found=True)
        return DraftAnswer(answer="Roughly 20,000 [1].", citations=[1], found=True)

    rewriter = FakeQueryRewriter(["final dividend recommended"])

    response, _ = await ask(
        pipeline(FakeAnswerGenerator(guess_then_read), rewriter), db_session, "payout"
    )

    assert [step.step for step in response.steps] == [
        "scope",
        "retrieve",
        "answer",
        "verify",
        "rewrite",
        "retrieve",
        "answer",
        "verify",
    ]
    assert response.answer == "A final dividend [1]."
    assert response.verified is True


async def test_an_empty_database_answers_without_calling_the_model(
    db_session: AsyncSession,
) -> None:
    generator = FakeAnswerGenerator(NOT_FOUND)
    rewriter = FakeQueryRewriter()

    response, sources = await ask(pipeline(generator, rewriter), db_session, "revenue")

    assert response.answer == "No reports have been ingested yet."
    assert (sources, generator.calls, rewriter.calls) == ([], [], [])


async def seed_two_companies(session: AsyncSession) -> None:
    """Four pages from Alpha, then one from Beta, all equally close to every query."""
    for company, ticker, pages in (("Alpha Ltd", "ALPHA", 4), ("Beta Corp", "BETA", 1)):
        session.add(
            Report(
                company=company,
                ticker=ticker,
                fiscal_year=2026,
                source_url=f"https://example.com/{ticker}.pdf",
                file_sha256=ticker.ljust(64, "0"),
                page_count=pages,
                chunks=[
                    Chunk(
                        page_number=page,
                        chunk_index=page,
                        kind="text",
                        content=f"{company} revenue for the year, page {page}.",
                        embedding=axis_vector(0),
                    )
                    for page in range(1, pages + 1)
                ],
            )
        )
    await session.commit()


async def test_a_question_naming_two_companies_gets_sources_from_both(
    db_session: AsyncSession,
) -> None:
    await seed_two_companies(db_session)
    generator = FakeAnswerGenerator(NOT_FOUND)
    agent = pipeline(generator, FakeQueryRewriter(), max_rewrites=0)

    final = await answer_question(agent, db_session, "Compare Alpha Ltd and BETA revenue", 2)

    assert final.response.steps[0].detail == "Searching Alpha Ltd and Beta Corp separately."
    assert {source.company for source in final.sources} == {"Alpha Ltd", "Beta Corp"}


async def test_a_question_naming_one_company_searches_only_its_reports(
    db_session: AsyncSession,
) -> None:
    await seed_two_companies(db_session)
    generator = FakeAnswerGenerator(NOT_FOUND)
    agent = pipeline(generator, FakeQueryRewriter(), max_rewrites=0)

    final = await answer_question(agent, db_session, "What was Beta Corp's revenue?", 3)

    assert final.response.steps[0].detail == "Searching the reports of Beta Corp."
    assert {source.company for source in final.sources} == {"Beta Corp"}


async def test_a_question_naming_no_company_searches_every_report(
    db_session: AsyncSession,
) -> None:
    await seed_two_companies(db_session)
    generator = FakeAnswerGenerator(NOT_FOUND)
    agent = pipeline(generator, FakeQueryRewriter(), max_rewrites=0)

    final = await answer_question(agent, db_session, "What was revenue for the year?", 5)

    assert final.response.steps[0].detail == "No company named, so searching every report."
    assert {source.company for source in final.sources} == {"Alpha Ltd", "Beta Corp"}
