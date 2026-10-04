import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.dataset import EvalQuestion
from app.evaluation.runner import QuestionResult, evaluate_question, summarise
from app.qa.baseline import BaselinePipeline, DraftAnswer
from app.retrieval.retriever import VectorRetriever
from tests.fakes import AxisEmbeddings, FakeAnswerGenerator
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio

ATTRITION = EvalQuestion(
    id="attrition",
    category="people",
    question="What was attrition?",
    type="text",
    accepted=["voluntary attrition"],
)
WORLD_CUP = EvalQuestion(
    id="world-cup", category="unanswerable", question="Who won?", answerable=False
)


async def run(
    session: AsyncSession, question: EvalQuestion, draft: DraftAnswer | None
) -> QuestionResult:
    await seed_report(session)
    pipeline = BaselinePipeline(
        VectorRetriever(AxisEmbeddings(query_axis=1)), FakeAnswerGenerator(draft)
    )
    return await evaluate_question(session, pipeline, question, top_k=2)


async def test_a_right_answer_citing_the_right_source_is_correct_and_supported(
    db_session: AsyncSession,
) -> None:
    draft = DraftAnswer(answer="Voluntary attrition fell [1].", citations=[1], found=True)

    result = await run(db_session, ATTRITION, draft)

    assert (result.correct, result.retrieved, result.supported) == (True, True, True)
    assert result.cited_pages == [2]


async def test_a_right_answer_citing_the_wrong_source_is_not_supported(
    db_session: AsyncSession,
) -> None:
    draft = DraftAnswer(answer="Voluntary attrition fell [2].", citations=[2], found=True)

    result = await run(db_session, ATTRITION, draft)

    assert (result.correct, result.retrieved, result.supported) == (True, True, False)


async def test_a_wrong_answer_is_incorrect_even_when_the_source_was_retrieved(
    db_session: AsyncSession,
) -> None:
    draft = DraftAnswer(answer="The sources do not say.", citations=[], found=True)

    result = await run(db_session, ATTRITION, draft)

    assert (result.correct, result.retrieved, result.supported) == (False, True, False)


async def test_an_unanswerable_question_is_correct_only_when_nothing_is_cited(
    db_session: AsyncSession,
) -> None:
    refused = await run(
        db_session, WORLD_CUP, DraftAnswer(answer="Not in the sources.", citations=[], found=True)
    )
    assert (refused.correct, refused.retrieved, refused.supported) == (True, None, None)


async def test_an_unanswerable_question_answered_with_a_citation_is_incorrect(
    db_session: AsyncSession,
) -> None:
    invented = await run(
        db_session, WORLD_CUP, DraftAnswer(answer="France [1].", citations=[1], found=True)
    )

    assert invented.correct is False


async def test_a_model_failure_is_recorded_as_an_error(db_session: AsyncSession) -> None:
    result = await run(db_session, ATTRITION, draft=None)

    assert (result.correct, result.error) == (False, "model unavailable")


def result(
    category: str, correct: bool, retrieved: bool | None, supported: bool | None
) -> QuestionResult:
    return QuestionResult(
        id="q",
        category=category,
        question="?",
        answer="",
        cited_pages=[],
        correct=correct,
        retrieved=retrieved,
        supported=supported,
        rewrites=0,
        verified=None,
        error=None,
        seconds=0.0,
    )


def test_summarise_counts_each_category_and_the_overall_total() -> None:
    summaries = summarise(
        [
            result("people", True, True, True),
            result("people", False, True, False),
            result("unanswerable", True, None, None),
        ]
    )

    assert [
        (s.label, s.total, s.correct, s.answerable, s.retrieved, s.supported) for s in summaries
    ] == [
        ("people", 2, 1, 2, 2, 1),
        ("unanswerable", 1, 1, 0, 0, 0),
        ("overall", 3, 2, 2, 2, 1),
    ]
