from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready")
async def ready(session: SessionDep) -> ReadinessResponse:
    try:
        version = await session.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    # asyncpg raises a plain OSError when the server is unreachable.
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Database is unreachable."
        ) from exc
    if version is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The pgvector extension is not installed."
        )
    return ReadinessResponse(status="ok", database="ok", pgvector_version=version)
