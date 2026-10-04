import asyncio

from langchain_core.embeddings import Embeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.retrieval.types import RetrievedChunk, to_retrieved


async def search_by_meaning(
    session: AsyncSession, embeddings: Embeddings, question: str, limit: int
) -> list[RetrievedChunk]:
    """Returns the chunks closest in meaning to the question, nearest first."""
    query_vector = await asyncio.to_thread(embeddings.embed_query, question)
    # Ordering by the raw distance is what lets PostgreSQL use the vector index.
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = await session.execute(
        select(Chunk, Report, (1 - distance).label("score"))
        .join(Chunk.report)
        .order_by(distance)
        .limit(limit)
    )
    return [to_retrieved(chunk, report, float(score)) for chunk, report, score in rows]
