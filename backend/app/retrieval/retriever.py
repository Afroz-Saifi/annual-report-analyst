import asyncio
from collections.abc import Sequence
from dataclasses import replace
from typing import Literal, Protocol

from langchain_core.embeddings import Embeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword import search_by_keywords
from app.retrieval.rerank import LocalReranker, Reranker
from app.retrieval.types import RetrievedChunk
from app.retrieval.vector import search_by_meaning

RetrievalMode = Literal["vector", "hybrid", "hybrid_rerank"]

# How many results each search contributes before fusion, and how many fused
# results the reranker reads. Larger pools find more but rerank more slowly.
CANDIDATES_PER_SEARCH = 30
RERANK_POOL = 30


class Retriever(Protocol):
    """Finds the sources best matching a question, optionally within some reports only."""

    async def retrieve(
        self,
        session: AsyncSession,
        question: str,
        limit: int,
        report_ids: Sequence[int] | None = None,
    ) -> list[RetrievedChunk]: ...


class VectorRetriever:
    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings

    async def retrieve(
        self,
        session: AsyncSession,
        question: str,
        limit: int,
        report_ids: Sequence[int] | None = None,
    ) -> list[RetrievedChunk]:
        return await search_by_meaning(session, self._embeddings, question, limit, report_ids)


class HybridRetriever:
    """Vector and keyword search fused by rank, optionally reordered by a reranker."""

    def __init__(self, embeddings: Embeddings, reranker: Reranker | None = None) -> None:
        self._embeddings = embeddings
        self._reranker = reranker

    async def retrieve(
        self,
        session: AsyncSession,
        question: str,
        limit: int,
        report_ids: Sequence[int] | None = None,
    ) -> list[RetrievedChunk]:
        by_meaning = await search_by_meaning(
            session, self._embeddings, question, CANDIDATES_PER_SEARCH, report_ids
        )
        by_keywords = await search_by_keywords(session, question, CANDIDATES_PER_SEARCH, report_ids)
        fused = reciprocal_rank_fusion([by_meaning, by_keywords])
        if self._reranker is None:
            return fused[:limit]

        pool = fused[:RERANK_POOL]
        scores = await asyncio.to_thread(
            self._reranker.score, question, [chunk.content for chunk in pool]
        )
        reranked = sorted(zip(pool, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        return [replace(chunk, score=score) for chunk, score in reranked[:limit]]


def build_retriever(mode: RetrievalMode, embeddings: Embeddings, reranker_model: str) -> Retriever:
    if mode == "vector":
        return VectorRetriever(embeddings)
    if mode == "hybrid":
        return HybridRetriever(embeddings)
    return HybridRetriever(embeddings, LocalReranker(reranker_model))
