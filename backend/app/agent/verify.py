from dataclasses import dataclass, field
from decimal import Decimal
from itertools import permutations

from app.core.numbers import number_tokens, numbers_in
from app.retrieval.types import RetrievedChunk


@dataclass(frozen=True)
class FigureCheck:
    # Figures found in neither a cited source nor the question, as written.
    unsupported: list[str]
    # Figures the answer worked out from two of its sourced figures, with how.
    derived: dict[str, str] = field(default_factory=dict)


def check_figures(answer: str, question: str, cited: list[RetrievedChunk]) -> FigureCheck:
    """Checks every figure in the answer against the cited sources.

    A figure missing from the sources still passes when it is the sum,
    difference or percentage change of two figures that the answer itself
    states and that the sources contain, so the answer shows its working.
    """
    allowed = numbers_in(question)
    for source in cited:
        allowed |= numbers_in(source.content)

    tokens = list(dict.fromkeys(number_tokens(answer)))
    sourced = [(text, value) for text, value in tokens if value in allowed]
    unsupported: list[str] = []
    derived: dict[str, str] = {}
    for text, value in tokens:
        if value in allowed:
            continue
        working = _working_for(text, value, sourced)
        if working:
            derived[text] = working
        else:
            unsupported.append(text)
    return FigureCheck(list(dict.fromkeys(unsupported)), derived)


def _working_for(text: str, value: Decimal, sourced: list[tuple[str, Decimal]]) -> str | None:
    # Compare at the precision the answer wrote the figure to.
    places = len(text.split(".")[1]) if "." in text else 0
    quantum = Decimal(1).scaleb(-places)
    for (a_text, a), (b_text, b) in permutations(sourced, 2):
        if (a - b).quantize(quantum) == value:
            return f"{text} = {a_text} - {b_text}"
        if (a + b).quantize(quantum) == value and a_text < b_text:
            return f"{text} = {a_text} + {b_text}"
        if b and ((a - b) / b * 100).quantize(quantum) == value:
            return f"{text}% = change from {b_text} to {a_text}"
    return None


def unsupported_figures(answer: str, question: str, cited: list[RetrievedChunk]) -> list[str]:
    return check_figures(answer, question, cited).unsupported
