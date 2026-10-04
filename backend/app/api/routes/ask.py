from fastapi import APIRouter, HTTPException, status

from app.api.deps import AnswerGeneratorDep, EmbeddingsDep, SessionDep
from app.qa.baseline import AnswerGenerationError, answer_question
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["questions"])


@router.post("/ask")
async def ask(
    request: AskRequest,
    session: SessionDep,
    embeddings: EmbeddingsDep,
    generator: AnswerGeneratorDep,
) -> AskResponse:
    try:
        return await answer_question(
            session, embeddings, generator, request.question, request.top_k
        )
    except AnswerGenerationError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The language model request failed."
        ) from exc
