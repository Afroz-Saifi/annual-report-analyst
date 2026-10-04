from app.core.numbers import numbers_in
from app.evaluation.dataset import EvalQuestion


def contains_accepted_answer(question: EvalQuestion, text: str) -> bool:
    if question.type == "number":
        found = numbers_in(text)
        return any(numbers_in(accepted) <= found for accepted in question.accepted)
    normalised = " ".join(text.casefold().split())
    return any(
        " ".join(accepted.casefold().split()) in normalised for accepted in question.accepted
    )
