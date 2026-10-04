from app.ingestion.chunk import CHUNK_SIZE, chunk_pages
from app.ingestion.parse import ParsedPage


def test_long_text_is_split_and_keeps_its_page_number() -> None:
    page = ParsedPage(number=7, text="Revenue grew this year. " * 200, tables=[])

    chunks = chunk_pages([page])

    assert len(chunks) > 1
    assert all(chunk.page_number == 7 and chunk.kind == "text" for chunk in chunks)
    assert all(len(chunk.content) <= CHUNK_SIZE for chunk in chunks)


def test_tables_stay_whole_even_when_longer_than_a_text_chunk() -> None:
    table = "| Metric | Value |\n| --- | --- |\n" + "| Row | 1 |\n" * 300
    page = ParsedPage(number=3, text="Short intro.", tables=[table])

    chunks = chunk_pages([page])

    assert [(chunk.kind, chunk.page_number) for chunk in chunks] == [("text", 3), ("table", 3)]
    assert chunks[1].content == table


def test_empty_page_produces_no_chunks() -> None:
    assert chunk_pages([ParsedPage(number=1, text="", tables=[])]) == []
