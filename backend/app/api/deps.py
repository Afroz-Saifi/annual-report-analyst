from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.qa.baseline import Pipeline
from app.qa.factory import build_pipeline


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@lru_cache
def get_pipeline() -> Pipeline:
    settings = get_settings()
    if settings.google_api_key is None or not settings.google_api_key.get_secret_value():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "GOOGLE_API_KEY is not set on the server."
        )
    return build_pipeline(
        settings,
        settings.google_api_key,
        settings.pipeline,
        settings.retrieval_mode,
        settings.expand_pages,
    )


SessionDep = Annotated[AsyncSession, Depends(get_session)]
PipelineDep = Annotated[Pipeline, Depends(get_pipeline)]
