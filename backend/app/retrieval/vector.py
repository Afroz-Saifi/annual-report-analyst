import asyncio
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    company: str
    fiscal_year: int
    source_url: str
    page_number: int
    kind: str
    content: str
    distance: float


async def search_chunks(
    session: AsyncSession, embeddings: Embeddings, question: str, limit: int
) -> list[RetrievedChunk]:
    """Returns the chunks closest in meaning to the question, nearest first."""
    query_vector = await asyncio.to_thread(embeddings.embed_query, question)
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    rows = await session.execute(
        select(Chunk, Report, distance).join(Chunk.report).order_by(distance).limit(limit)
    )
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            company=report.company,
            fiscal_year=report.fiscal_year,
            source_url=report.source_url,
            page_number=chunk.page_number,
            kind=chunk.kind,
            content=chunk.content,
            distance=float(row_distance),
        )
        for chunk, report, row_distance in rows
    ]
