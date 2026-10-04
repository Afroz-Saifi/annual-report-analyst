from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import PipelineDep, SessionDep
from app.qa.baseline import AnswerGenerationError, FinalAnswer, answer_question
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["questions"])

MODEL_FAILED = "The language model request failed."


@router.post("/ask")
async def ask(request: AskRequest, session: SessionDep, pipeline: PipelineDep) -> AskResponse:
    try:
        final = await answer_question(pipeline, session, request.question, request.top_k)
    except AnswerGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, MODEL_FAILED) from exc
    return final.response


@router.post("/ask/stream", response_class=EventSourceResponse)
async def ask_stream(
    request: AskRequest, session: SessionDep, pipeline: PipelineDep
) -> AsyncIterator[ServerSentEvent]:
    """Sends a `step` event as the agent works, then one `answer` or `error` event."""
    try:
        async for event in pipeline.stream(session, request.question, request.top_k):
            if isinstance(event, FinalAnswer):
                yield ServerSentEvent(event="answer", data=event.response)
            else:
                yield ServerSentEvent(event="step", data=event)
    except AnswerGenerationError:
        # The response has already started, so the failure travels as an event.
        yield ServerSentEvent(event="error", data={"detail": MODEL_FAILED})
