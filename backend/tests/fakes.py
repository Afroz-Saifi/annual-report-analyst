from langchain_core.embeddings import Embeddings

from app.db.models import EMBEDDING_DIM
from app.qa.baseline import AnswerGenerationError, DraftAnswer
from app.retrieval.vector import RetrievedChunk


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
    def __init__(self, draft: DraftAnswer | None = None) -> None:
        self.draft = draft
        self.seen_sources: list[RetrievedChunk] = []

    async def generate(self, question: str, sources: list[RetrievedChunk]) -> DraftAnswer:
        self.seen_sources = sources
        if self.draft is None:
            raise AnswerGenerationError("model unavailable")
        return self.draft
