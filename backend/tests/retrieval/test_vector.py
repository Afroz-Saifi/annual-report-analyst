import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.vector import search_by_meaning
from tests.fakes import AxisEmbeddings
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio


async def test_search_returns_the_nearest_chunk_first_with_its_report(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    results = await search_by_meaning(db_session, AxisEmbeddings(query_axis=1), "?", limit=3)

    assert len(results) == 3
    nearest = results[0]
    assert (nearest.page_number, nearest.kind) == (2, "table")
    assert (nearest.company, nearest.fiscal_year) == ("Sample Ltd", 2025)
    assert nearest.score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.0)


async def test_search_respects_the_limit(db_session: AsyncSession) -> None:
    await seed_report(db_session)

    results = await search_by_meaning(db_session, AxisEmbeddings(), "anything", limit=2)

    assert len(results) == 2


async def test_search_on_an_empty_database_returns_nothing(db_session: AsyncSession) -> None:
    assert await search_by_meaning(db_session, AxisEmbeddings(), "anything", limit=5) == []
