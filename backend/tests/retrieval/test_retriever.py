import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.retriever import HybridRetriever, VectorRetriever
from tests.fakes import AxisEmbeddings, KeywordCountReranker
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio


async def test_vector_retriever_returns_the_nearest_chunk(db_session: AsyncSession) -> None:
    await seed_report(db_session)

    results = await VectorRetriever(AxisEmbeddings(query_axis=2)).retrieve(db_session, "?", 1)

    assert [chunk.page_number for chunk in results] == [3]


async def test_hybrid_retriever_puts_a_chunk_found_by_both_searches_first(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    retriever = HybridRetriever(AxisEmbeddings(query_axis=1))

    results = await retriever.retrieve(db_session, "voluntary attrition", limit=3)

    assert results[0].page_number == 2
    assert len({chunk.chunk_id for chunk in results}) == len(results) == 3


async def test_hybrid_retriever_finds_a_keyword_match_that_vector_search_ranks_last(
    db_session: AsyncSession,
) -> None:
    await seed_report(db_session)
    # The query vector points at page 1, but the words only appear on page 3.
    retriever = HybridRetriever(AxisEmbeddings(query_axis=0))

    results = await retriever.retrieve(db_session, "final dividend", limit=2)

    assert {chunk.page_number for chunk in results} == {1, 3}


async def test_the_reranker_decides_the_final_order(db_session: AsyncSession) -> None:
    await seed_report(db_session)
    retriever = HybridRetriever(AxisEmbeddings(query_axis=0), KeywordCountReranker("dividend"))

    results = await retriever.retrieve(db_session, "revenue", limit=2)

    assert results[0].page_number == 3
    assert results[0].score == 1.0
