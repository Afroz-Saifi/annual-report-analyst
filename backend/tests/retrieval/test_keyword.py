import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.keyword import search_by_keywords
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio


async def test_keyword_search_finds_the_chunk_sharing_the_question_words(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    results = await search_by_keywords(db_session, "What was voluntary attrition?", limit=5)

    assert [chunk.page_number for chunk in results] == [2]
    assert results[0].score > 0


async def test_keyword_search_matches_any_word_and_ranks_more_matches_first(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    results = await search_by_keywords(
        db_session, "final dividend recommended versus revenue", limit=5
    )

    assert [chunk.page_number for chunk in results] == [3, 1]


async def test_keyword_search_matches_word_forms(db_session: AsyncSession) -> None:
    await seed_report(db_session)

    results = await search_by_keywords(db_session, "dividends recommending", limit=5)

    assert [chunk.page_number for chunk in results] == [3]


async def test_keyword_search_with_no_matching_words_returns_nothing(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)

    assert await search_by_keywords(db_session, "football world cup", limit=5) == []
