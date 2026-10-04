import re
from decimal import Decimal

from app.evaluation.dataset import EvalQuestion

_CITATION_MARKER = re.compile(r"\[\d+\]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[Decimal]:
    """Every number in the text, so that 1,78,650 and 178650.0 compare equal."""
    without_markers = _CITATION_MARKER.sub(" ", text)
    return {Decimal(match.replace(",", "")) for match in _NUMBER.findall(without_markers)}


def contains_accepted_answer(question: EvalQuestion, text: str) -> bool:
    if question.type == "number":
        found = numbers_in(text)
        return any(numbers_in(accepted) <= found for accepted in question.accepted)
    normalised = " ".join(text.casefold().split())
    return any(
        " ".join(accepted.casefold().split()) in normalised for accepted in question.accepted
    )
