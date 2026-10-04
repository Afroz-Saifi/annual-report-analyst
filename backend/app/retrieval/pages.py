from collections.abc import Sequence
from dataclasses import replace

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.retrieval.retriever import Retriever
from app.retrieval.types import RetrievedChunk

# Longest shared run looked for between neighbouring chunks. It only needs to
# exceed the overlap the chunker leaves between them.
MAX_OVERLAP = 400


class PageExpandingRetriever:
    """Searches by chunk but returns whole pages.

    A statement or table spans several chunks, and the chunk that matches the
    question is often not the one holding the figure. Each hit is therefore
    replaced by the full text of its page, once per page, in hit order.
    """

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner

    async def retrieve(
        self,
        session: AsyncSession,
        question: str,
        limit: int,
        report_ids: Sequence[int] | None = None,
    ) -> list[RetrievedChunk]:
        hits = await self._inner.retrieve(session, question, limit, report_ids)
        first_hit_per_page: dict[tuple[int, int], RetrievedChunk] = {}
        for hit in hits:
            first_hit_per_page.setdefault((hit.report_id, hit.page_number), hit)
        if not first_hit_per_page:
            return []

        rows = await session.execute(
            select(Chunk.report_id, Chunk.page_number, Chunk.kind, Chunk.content)
            .where(tuple_(Chunk.report_id, Chunk.page_number).in_(first_hit_per_page))
            .order_by(Chunk.chunk_index)
        )
        text: dict[tuple[int, int], list[str]] = {page: [] for page in first_hit_per_page}
        tables: dict[tuple[int, int], list[str]] = {page: [] for page in first_hit_per_page}
        for report_id, page_number, kind, content in rows:
            (tables if kind == "table" else text)[(report_id, page_number)].append(content)

        return [
            replace(
                hit, kind="page", content="\n\n".join([join_overlapping(text[page]), *tables[page]])
            )
            for page, hit in first_hit_per_page.items()
        ]


def join_overlapping(pieces: list[str]) -> str:
    """Joins consecutive chunks of one page, dropping the text they share."""
    joined = ""
    for piece in pieces:
        longest = min(len(joined), len(piece), MAX_OVERLAP)
        overlap = next((size for size in range(longest, 0, -1) if joined.endswith(piece[:size])), 0)
        separator = "\n" if joined and not overlap else ""
        joined += separator + piece[overlap:]
    return joined
