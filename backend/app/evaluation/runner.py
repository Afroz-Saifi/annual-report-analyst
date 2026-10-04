import time
from dataclasses import dataclass

from langchain_core.callbacks import get_usage_metadata_callback
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.dataset import EvalQuestion
from app.evaluation.scoring import contains_accepted_answer
from app.qa.baseline import AnswerGenerationError, FinalAnswer, Pipeline, answer_question


@dataclass(frozen=True)
class QuestionResult:
    id: str
    category: str
    question: str
    answer: str
    cited_pages: list[int]
    correct: bool
    # For answerable questions: was the accepted answer among the retrieved
    # sources, and among the sources the answer cited. None when unanswerable.
    retrieved: bool | None
    supported: bool | None
    rewrites: int
    verified: bool | None
    error: str | None
    seconds: float
    # Summed over every model call the question needed. Output includes the
    # model's reasoning ("thinking") tokens, which are billed as output.
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Summary:
    label: str
    total: int
    correct: int
    answerable: int
    retrieved: int
    supported: int


async def evaluate_question(
    session: AsyncSession,
    pipeline: Pipeline,
    question: EvalQuestion,
    top_k: int,
) -> QuestionResult:
    started = time.perf_counter()
    final: FinalAnswer | None = None
    error = ""
    with get_usage_metadata_callback() as usage:
        try:
            final = await answer_question(pipeline, session, question.question, top_k)
        except AnswerGenerationError as exc:
            error = str(exc)
    input_tokens = sum(model["input_tokens"] for model in usage.usage_metadata.values())
    output_tokens = sum(model["output_tokens"] for model in usage.usage_metadata.values())

    if final is None:
        return QuestionResult(
            id=question.id,
            category=question.category,
            question=question.question,
            answer="",
            cited_pages=[],
            correct=False,
            retrieved=None,
            supported=None,
            rewrites=0,
            verified=None,
            error=error,
            seconds=time.perf_counter() - started,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    response, sources = final.response, final.sources
    cited = [sources[citation.source - 1] for citation in response.citations]
    if question.answerable:
        correct = contains_accepted_answer(question, response.answer)
        # Taken across all the sources together, since a comparison draws its
        # figures from several pages.
        retrieved: bool | None = contains_accepted_answer(
            question, "\n".join(source.content for source in sources)
        )
        supported: bool | None = correct and contains_accepted_answer(
            question, "\n".join(source.content for source in cited)
        )
    else:
        # The right response to an unanswerable question is to cite nothing.
        correct, retrieved, supported = not cited, None, None

    return QuestionResult(
        id=question.id,
        category=question.category,
        question=question.question,
        answer=response.answer,
        cited_pages=[source.page_number for source in cited],
        correct=correct,
        retrieved=retrieved,
        supported=supported,
        rewrites=sum(step.step == "rewrite" for step in response.steps),
        verified=response.verified,
        error=None,
        seconds=time.perf_counter() - started,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def summarise(results: list[QuestionResult]) -> list[Summary]:
    """One row per category, in first-seen order, followed by an overall row."""
    categories = list(dict.fromkeys(result.category for result in results))
    groups = [(category, [r for r in results if r.category == category]) for category in categories]
    groups.append(("overall", results))
    return [
        Summary(
            label=label,
            total=len(group),
            correct=sum(r.correct for r in group),
            answerable=sum(r.retrieved is not None for r in group),
            retrieved=sum(bool(r.retrieved) for r in group),
            supported=sum(bool(r.supported) for r in group),
        )
        for label, group in groups
    ]
