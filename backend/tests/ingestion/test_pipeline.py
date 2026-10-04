from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EMBEDDING_DIM, Chunk, Report
from app.ingestion.manifest import ReportEntry
from app.ingestion.pipeline import ingest_report

pytestmark = pytest.mark.anyio

ENTRY = ReportEntry(
    company="Sample Ltd",
    ticker="SAMPLE",
    fiscal_year=2025,
    source_url="https://example.com/sample-report.pdf",
    file="sample-report.pdf",
)


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIM


async def test_ingest_stores_report_and_chunks(db_session: AsyncSession, sample_pdf: Path) -> None:
    result = await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)

    assert (result.status, result.pages, result.table_chunks) == ("ingested", 2, 1)
    report = (await db_session.scalars(select(Report))).one()
    assert (report.company, report.page_count) == ("Sample Ltd", 2)
    assert report.file_name == "sample-report.pdf"
    chunks = (await db_session.scalars(select(Chunk).order_by(Chunk.chunk_index))).all()
    assert [chunk.kind for chunk in chunks] == ["text", "text", "table"]
    assert [chunk.page_number for chunk in chunks] == [1, 2, 2]
    assert "Headcount" in chunks[2].content


async def test_ingesting_the_same_file_twice_is_a_no_op(
    db_session: AsyncSession, sample_pdf: Path
) -> None:
    await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)

    result = await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)

    assert result.status == "unchanged"
    assert await db_session.scalar(select(func.count()).select_from(Report)) == 1


async def test_re_running_records_a_file_name_missing_from_an_older_ingest(
    db_session: AsyncSession, sample_pdf: Path
) -> None:
    await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)
    report = (await db_session.scalars(select(Report))).one()
    report.file_name = None
    await db_session.commit()

    result = await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)

    assert result.status == "unchanged"
    await db_session.refresh(report)
    assert report.file_name == "sample-report.pdf"


@pytest.fixture
def revised_pdf(sample_pdf: Path, tmp_path: Path) -> Path:
    path = tmp_path / "revised.pdf"
    path.write_bytes(sample_pdf.read_bytes() + b"\n% revised")
    return path


async def test_a_changed_file_replaces_the_old_chunks(
    db_session: AsyncSession, sample_pdf: Path, revised_pdf: Path
) -> None:
    await ingest_report(db_session, FakeEmbeddings(), ENTRY, sample_pdf)
    before = await db_session.scalar(select(func.count()).select_from(Chunk))

    result = await ingest_report(db_session, FakeEmbeddings(), ENTRY, revised_pdf)

    assert result.status == "ingested"
    assert await db_session.scalar(select(func.count()).select_from(Report)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Chunk)) == before
