from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings


class LocalEmbeddings(Embeddings):
    """Runs an open-source embedding model on this machine through ONNX."""

    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._model.query_embed(text)))
        return list(vector.tolist())
