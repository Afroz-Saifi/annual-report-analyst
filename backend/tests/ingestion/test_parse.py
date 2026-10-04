from pathlib import Path

from app.ingestion.parse import Table, is_usable_table, parse_pdf, table_to_markdown


def test_table_to_markdown_builds_header_and_rows() -> None:
    table: Table = [["Metric", "FY24", "FY25"], ["Headcount", "1,000", "1,200"]]

    assert table_to_markdown(table) == (
        "| Metric | FY24 | FY25 |\n| --- | --- | --- |\n| Headcount | 1,000 | 1,200 |"
    )


def test_table_to_markdown_cleans_cells_and_pads_short_rows() -> None:
    table: Table = [["Line\nitem", "A|B"], [None]]

    assert table_to_markdown(table) == "| Line item | A\\|B |\n| --- | --- |\n|  |  |"


def test_single_row_or_single_column_tables_are_not_usable() -> None:
    assert not is_usable_table([["only", "one", "row"]])
    assert not is_usable_table([["one"], ["column"]])
    assert is_usable_table([["a", "b"], ["c", "d"]])


def test_tables_with_only_empty_cells_are_not_usable() -> None:
    assert not is_usable_table([[None, ""], [" ", None]])


def test_parse_pdf_keeps_page_numbers_text_and_tables(sample_pdf: Path) -> None:
    pages = parse_pdf(sample_pdf)

    assert [page.number for page in pages] == [1, 2]
    assert "Revenue grew steadily" in pages[0].text
    assert pages[0].tables == []
    assert pages[1].tables == [
        "| Metric | FY24 | FY25 |\n| --- | --- | --- |\n| Headcount | 1,000 | 1,200 |"
    ]
