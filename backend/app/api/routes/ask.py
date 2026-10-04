from fastapi import APIRouter, HTTPException, status

from app.api.deps import PipelineDep, SessionDep
from app.qa.baseline import AnswerGenerationError
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["questions"])


@router.post("/ask")
async def ask(request: AskRequest, session: SessionDep, pipeline: PipelineDep) -> AskResponse:
    try:
        response, _ = await pipeline.answer(session, request.question, request.top_k)
    except AnswerGenerationError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The language model request failed."
        ) from exc
    return response
