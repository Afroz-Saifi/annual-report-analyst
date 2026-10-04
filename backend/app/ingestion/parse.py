from dataclasses import dataclass
from pathlib import Path

import pdfplumber

Table = list[list[str | None]]


@dataclass(frozen=True)
class ParsedPage:
    number: int
    text: str
    tables: list[str]


def parse_pdf(path: Path) -> list[ParsedPage]:
    with pdfplumber.open(path) as pdf:
        return [
            ParsedPage(
                number=number,
                text=page.extract_text() or "",
                tables=[
                    table_to_markdown(table)
                    for table in page.extract_tables()
                    if is_usable_table(table)
                ],
            )
            for number, page in enumerate(pdf.pages, start=1)
        ]


def is_usable_table(table: Table) -> bool:
    has_shape = len(table) >= 2 and max(len(row) for row in table) >= 2
    # Decorative grids are detected as tables with every cell empty.
    return has_shape and any(cell and cell.strip() for row in table for cell in row)


def table_to_markdown(table: Table) -> str:
    width = max(len(row) for row in table)
    rows = [[_clean(cell) for cell in row] + [""] * (width - len(row)) for row in table]
    header, *body = rows
    lines = [_row(header), _row(["---"] * width), *(_row(row) for row in body)]
    return "\n".join(lines)


def _clean(cell: str | None) -> str:
    return " ".join((cell or "").split()).replace("|", "\\|")


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"
