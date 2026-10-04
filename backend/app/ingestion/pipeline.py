import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.embeddings import Embeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.ingestion.chunk import chunk_pages
from app.ingestion.manifest import ReportEntry
from app.ingestion.parse import parse_pdf


@dataclass(frozen=True)
class IngestResult:
    status: Literal["ingested", "unchanged"]
    pages: int
    text_chunks: int
    table_chunks: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def ingest_report(
    session: AsyncSession, embeddings: Embeddings, entry: ReportEntry, pdf_path: Path
) -> IngestResult:
    file_sha256 = await asyncio.to_thread(_sha256, pdf_path)

    existing = await session.scalar(
        select(Report).where(Report.ticker == entry.ticker, Report.fiscal_year == entry.fiscal_year)
    )
    if existing is not None:
        if existing.file_sha256 == file_sha256:
            if existing.file_name != entry.file:
                existing.file_name = entry.file
                await session.commit()
            return IngestResult(
                status="unchanged", pages=existing.page_count, text_chunks=0, table_chunks=0
            )
        await session.delete(existing)
        await session.flush()

    pages = await asyncio.to_thread(parse_pdf, pdf_path)
    drafts = chunk_pages(pages)
    vectors = await asyncio.to_thread(
        embeddings.embed_documents, [draft.content for draft in drafts]
    )

    report = Report(
        company=entry.company,
        ticker=entry.ticker,
        fiscal_year=entry.fiscal_year,
        source_url=entry.source_url,
        file_sha256=file_sha256,
        file_name=entry.file,
        page_count=len(pages),
        chunks=[
            Chunk(
                page_number=draft.page_number,
                chunk_index=index,
                kind=draft.kind,
                content=draft.content,
                embedding=vector,
            )
            for index, (draft, vector) in enumerate(zip(drafts, vectors, strict=True))
        ],
    )
    session.add(report)
    await session.commit()

    table_chunks = sum(draft.kind == "table" for draft in drafts)
    return IngestResult(
        status="ingested",
        pages=len(pages),
        text_chunks=len(drafts) - table_chunks,
        table_chunks=table_chunks,
    )
