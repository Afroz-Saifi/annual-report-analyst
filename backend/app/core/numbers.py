import re
from decimal import Decimal

_CITATION_MARKER = re.compile(r"\[\d+\]")
# A number that does not continue a word or another number, so the 26 in
# "FY26" and the 2 in "Q2" are not read as figures.
_NUMBER = re.compile(r"(?<![A-Za-z\d.,])\d[\d,]*(?:\.\d+)?")


def number_tokens(text: str) -> list[tuple[str, Decimal]]:
    """Every figure in the text as written, with its value. Citation markers are skipped."""
    without_markers = _CITATION_MARKER.sub(" ", text)
    return [
        (match.rstrip(","), Decimal(match.replace(",", "")))
        for match in _NUMBER.findall(without_markers)
    ]


def numbers_in(text: str) -> set[Decimal]:
    """Every figure in the text, so that 1,78,650 and 178650.0 compare equal."""
    return {value for _, value in number_tokens(text)}
