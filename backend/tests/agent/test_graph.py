import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import AgentPipeline, build_agent
from app.qa.baseline import DraftAnswer
from app.retrieval.retriever import HybridRetriever
from app.retrieval.types import RetrievedChunk
from tests.fakes import AxisEmbeddings, FakeAnswerGenerator, FakeQueryRewriter
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


async def test_an_answer_found_on_the_first_search_needs_no_rewrite(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(
        DraftAnswer(answer="Revenue grew [1].", citations=[1], found=True)
    )
    rewriter = FakeQueryRewriter()

    response, sources = await pipeline(generator, rewriter).answer(db_session, "revenue", top_k=1)

    assert response.answer == "Revenue grew [1]."
    assert [step.step for step in response.steps] == ["retrieve", "answer", "verify"]
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

    response, sources = await pipeline(generator, rewriter).answer(
        db_session, "payout to shareholders", top_k=1
    )

    assert [step.step for step in response.steps] == [
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

    response, _ = await pipeline(generator, rewriter, max_rewrites=2).answer(
        db_session, "football world cup", top_k=1
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

    response, _ = await pipeline(generator, FakeQueryRewriter(), max_rewrites=0).answer(
        db_session, "revenue", top_k=1
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

    response, _ = await pipeline(FakeAnswerGenerator(guess_then_read), rewriter).answer(
        db_session, "payout", top_k=1
    )

    assert [step.step for step in response.steps] == [
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

    response, sources = await pipeline(generator, rewriter).answer(db_session, "revenue", top_k=1)

    assert response.answer == "No reports have been ingested yet."
    assert (sources, generator.calls, rewriter.calls) == ([], [], [])
