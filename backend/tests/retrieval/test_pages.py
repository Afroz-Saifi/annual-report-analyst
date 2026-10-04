import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.retrieval.pages import PageExpandingRetriever, join_overlapping
from app.retrieval.retriever import VectorRetriever
from tests.fakes import AxisEmbeddings, axis_vector

pytestmark = pytest.mark.anyio


def test_join_overlapping_drops_the_shared_text_between_neighbours() -> None:
    pieces = ["Revenue from operations 1,78,650\nOther income 4,322", "Other income 4,322\nTotal"]

    assert join_overlapping(pieces) == "Revenue from operations 1,78,650\nOther income 4,322\nTotal"


def test_join_overlapping_keeps_chunks_that_share_nothing_on_separate_lines() -> None:
    assert join_overlapping(["first part", "second part"]) == "first part\nsecond part"
    assert join_overlapping([]) == ""


async def seed_two_page_report(session: AsyncSession) -> None:
    chunks = [
        (5, "text", "Cash flow statement. Profit for the year 29,474", 0),
        (5, "text", "Profit for the year 29,474\nNet cash from operations 33,986", 1),
        (5, "table", "| Item | FY26 |\n| --- | --- |\n| Net cash | 33,986 |", 1),
        (6, "text", "Notes to the accounts.", 2),
    ]
    session.add(
        Report(
            company="Sample Ltd",
            ticker="SAMPLE",
            fiscal_year=2026,
            source_url="https://example.com/sample.pdf",
            file_sha256="0" * 64,
            page_count=6,
            chunks=[
                Chunk(
                    page_number=page,
                    chunk_index=index,
                    kind=kind,
                    content=content,
                    embedding=axis_vector(axis),
                )
                for index, (page, kind, content, axis) in enumerate(chunks)
            ],
        )
    )
    await session.commit()


async def test_a_hit_is_replaced_by_the_whole_text_of_its_page(db_session: AsyncSession) -> None:
    await seed_two_page_report(db_session)
    retriever = PageExpandingRetriever(VectorRetriever(AxisEmbeddings(query_axis=0)))

    results = await retriever.retrieve(db_session, "cash flow", limit=1)

    assert [(page.page_number, page.kind) for page in results] == [(5, "page")]
    assert results[0].content == (
        "Cash flow statement. Profit for the year 29,474\nNet cash from operations 33,986"
        "\n\n| Item | FY26 |\n| --- | --- |\n| Net cash | 33,986 |"
    )


async def test_several_hits_on_one_page_become_a_single_page(db_session: AsyncSession) -> None:
    await seed_two_page_report(db_session)
    retriever = PageExpandingRetriever(VectorRetriever(AxisEmbeddings(query_axis=1)))

    results = await retriever.retrieve(db_session, "net cash", limit=4)

    assert [page.page_number for page in results] == [5, 6]


async def test_no_hits_gives_no_pages(db_session: AsyncSession) -> None:
    retriever = PageExpandingRetriever(VectorRetriever(AxisEmbeddings()))

    assert await retriever.retrieve(db_session, "anything", limit=3) == []
