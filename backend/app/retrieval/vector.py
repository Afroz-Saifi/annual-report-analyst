import asyncio
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.retrieval.types import RetrievedChunk, to_retrieved


async def search_by_meaning(
    session: AsyncSession,
    embeddings: Embeddings,
    question: str,
    limit: int,
    report_ids: Sequence[int] | None = None,
) -> list[RetrievedChunk]:
    """Returns the chunks closest in meaning to the question, nearest first."""
    query_vector = await asyncio.to_thread(embeddings.embed_query, question)
    # Ordering by the raw distance is what lets PostgreSQL use the vector index.
    distance = Chunk.embedding.cosine_distance(query_vector)
    statement = (
        select(Chunk, Report, (1 - distance).label("score"))
        .join(Chunk.report)
        .order_by(distance)
        .limit(limit)
    )
    if report_ids is not None:
        # The index filters after it searches, so a narrow filter can leave too
        # few rows. An iterative scan keeps searching until the limit is met,
        # at the cost of slightly unordered results, which are re-sorted below.
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        statement = statement.where(Chunk.report_id.in_(report_ids))
    rows = await session.execute(statement)
    results = [to_retrieved(chunk, report, float(score)) for chunk, report, score in rows]
    return sorted(results, key=lambda chunk: chunk.score, reverse=True)
