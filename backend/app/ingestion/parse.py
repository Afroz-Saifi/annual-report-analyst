import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

Table = list[list[str | None]]

TEXT_X_TOLERANCE = 5


@dataclass(frozen=True)
class ParsedPage:
    number: int
    text: str
    tables: list[str]


def parse_pdf(path: Path, rupee_glyphs: Sequence[str] = ()) -> list[ParsedPage]:
    """Reads every page's text and tables.

    `rupee_glyphs` names letters this report's fonts draw as ₹, such as the H
    in "H1,234 crore". They differ by report, so they are set per report.
    """

    def fix(text: str) -> str:
        return fix_rupee_sign(text, rupee_glyphs)

    with pdfplumber.open(path) as pdf:
        return [
            ParsedPage(
                number=number,
                # Some reports space the characters of a figure so widely that
                # the default tolerance splits "6,17,437" into "6,17 ,437".
                text=fix(page.extract_text(x_tolerance=TEXT_X_TOLERANCE) or ""),
                tables=[
                    table_to_markdown(table, fix)
                    for table in page.extract_tables()
                    if is_usable_table(table)
                ],
            )
            for number, page in enumerate(pdf.pages, start=1)
        ]


def fix_rupee_sign(text: str, glyphs: Sequence[str] = ()) -> str:
    # Many Indian reports draw ₹ with a font that maps the glyph to a backtick,
    # so "`1,78,650 crore" is extracted where the page shows "₹1,78,650 crore".
    text = text.replace("`", "₹")
    for glyph in glyphs:
        # Only where ₹ belongs: before a figure, or in a unit label such as
        # "(H in crore)", never inside a word or a reference number.
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(glyph)}(?= ?\d)", "₹", text)
        text = re.sub(rf"\({re.escape(glyph)}(?=\)| (?:in )?(?:crores?|lakhs?)\b)", "(₹", text)
    return text


def is_usable_table(table: Table) -> bool:
    has_shape = len(table) >= 2 and max(len(row) for row in table) >= 2
    # Decorative grids are detected as tables with every cell empty.
    return has_shape and any(cell and cell.strip() for row in table for cell in row)


def table_to_markdown(table: Table, fix: Callable[[str], str] = fix_rupee_sign) -> str:
    width = max(len(row) for row in table)
    rows = [[_clean(cell, fix) for cell in row] + [""] * (width - len(row)) for row in table]
    header, *body = rows
    lines = [_row(header), _row(["---"] * width), *(_row(row) for row in body)]
    return "\n".join(lines)


def _clean(cell: str | None, fix: Callable[[str], str]) -> str:
    return fix(" ".join((cell or "").split())).replace("|", "\\|")


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"
