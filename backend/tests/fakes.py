from collections.abc import Callable

from langchain_core.embeddings import Embeddings

from app.db.models import EMBEDDING_DIM
from app.qa.baseline import AnswerGenerationError, DraftAnswer
from app.retrieval.types import RetrievedChunk


def axis_vector(axis: int) -> list[float]:
    return [1.0 if index == axis else 0.0 for index in range(EMBEDDING_DIM)]


class AxisEmbeddings(Embeddings):
    """Embeds every query onto one axis, so tests control which chunk is nearest."""

    def __init__(self, query_axis: int = 0) -> None:
        self.query_axis = query_axis

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [axis_vector(0) for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return axis_vector(self.query_axis)


class FakeAnswerGenerator:
    """Returns a fixed draft, or whatever the given function makes of the sources."""

    def __init__(
        self, draft: DraftAnswer | Callable[[list[RetrievedChunk]], DraftAnswer] | None = None
    ) -> None:
        self.draft = draft
        self.calls: list[list[RetrievedChunk]] = []

    async def generate(self, question: str, sources: list[RetrievedChunk]) -> DraftAnswer:
        self.calls.append(sources)
        if self.draft is None:
            raise AnswerGenerationError("model unavailable")
        return self.draft(sources) if callable(self.draft) else self.draft


class FakeQueryRewriter:
    def __init__(self, *rounds: list[str]) -> None:
        self.rounds = list(rounds)
        self.calls: list[list[str]] = []

    async def rewrite(self, question: str, tried: list[str]) -> list[str]:
        self.calls.append(tried)
        return self.rounds.pop(0)


class KeywordCountReranker:
    """Scores a passage by how often it contains the given word."""

    def __init__(self, word: str) -> None:
        self.word = word

    def score(self, question: str, passages: list[str]) -> list[float]:
        return [float(passage.count(self.word)) for passage in passages]
