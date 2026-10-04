from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.embed import LocalEmbeddings
from app.qa.baseline import AnswerGenerator, GeminiAnswerGenerator
from app.retrieval.retriever import Retriever, build_retriever


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@lru_cache
def get_retriever() -> Retriever:
    settings = get_settings()
    return build_retriever(
        settings.retrieval_mode, LocalEmbeddings(settings.embedding_model), settings.reranker_model
    )


@lru_cache
def get_answer_generator() -> AnswerGenerator:
    settings = get_settings()
    if settings.google_api_key is None or not settings.google_api_key.get_secret_value():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "GOOGLE_API_KEY is not set on the server."
        )
    return GeminiAnswerGenerator(settings.llm_model, settings.google_api_key)


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RetrieverDep = Annotated[Retriever, Depends(get_retriever)]
AnswerGeneratorDep = Annotated[AnswerGenerator, Depends(get_answer_generator)]
