from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder


class Reranker(Protocol):
    def score(self, question: str, passages: list[str]) -> list[float]: ...


class LocalReranker:
    """Scores each passage against the question with a cross-encoder run locally."""

    def __init__(self, model_name: str) -> None:
        self._model = TextCrossEncoder(model_name)

    def score(self, question: str, passages: list[str]) -> list[float]:
        return [float(score) for score in self._model.rerank(question, passages)]
