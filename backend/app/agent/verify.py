from app.core.numbers import number_tokens, numbers_in
from app.retrieval.types import RetrievedChunk


def unsupported_figures(answer: str, question: str, cited: list[RetrievedChunk]) -> list[str]:
    """Figures in the answer that appear in neither a cited source nor the question."""
    allowed = numbers_in(question)
    for source in cited:
        allowed |= numbers_in(source.content)
    unsupported = [text for text, value in number_tokens(answer) if value not in allowed]
    return list(dict.fromkeys(unsupported))
