import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.retrieval.vector import search_chunks
from tests.fakes import AxisEmbeddings, axis_vector

pytestmark = pytest.mark.anyio


async def seed_report(session: AsyncSession) -> None:
    session.add(
        Report(
            company="Sample Ltd",
            ticker="SAMPLE",
            fiscal_year=2025,
            source_url="https://example.com/sample.pdf",
            file_sha256="0" * 64,
            page_count=3,
            chunks=[
                Chunk(
                    page_number=1,
                    chunk_index=0,
                    kind="text",
                    content="about revenue",
                    embedding=axis_vector(0),
                ),
                Chunk(
                    page_number=2,
                    chunk_index=1,
                    kind="table",
                    content="about attrition",
                    embedding=axis_vector(1),
                ),
                Chunk(
                    page_number=3,
                    chunk_index=2,
                    kind="text",
                    content="about dividends",
                    embedding=axis_vector(2),
                ),
            ],
        )
    )
    await session.commit()


async def test_search_returns_the_nearest_chunk_first_with_its_report(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    results = await search_chunks(db_session, AxisEmbeddings(query_axis=1), "attrition?", limit=3)

    assert len(results) == 3
    nearest = results[0]
    assert (nearest.content, nearest.page_number, nearest.kind) == ("about attrition", 2, "table")
    assert (nearest.company, nearest.fiscal_year) == ("Sample Ltd", 2025)
    assert nearest.distance == pytest.approx(0.0)
    assert results[1].distance == pytest.approx(1.0)


async def test_search_respects_the_limit(db_session: AsyncSession) -> None:
    await seed_report(db_session)

    results = await search_chunks(db_session, AxisEmbeddings(), "anything", limit=2)

    assert len(results) == 2


async def test_search_on_an_empty_database_returns_nothing(db_session: AsyncSession) -> None:
    assert await search_chunks(db_session, AxisEmbeddings(), "anything", limit=5) == []
