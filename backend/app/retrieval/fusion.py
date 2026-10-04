from collections import defaultdict
from dataclasses import replace

from app.retrieval.types import RetrievedChunk

# The constant from the original Reciprocal Rank Fusion paper. It damps the
# gap between adjacent ranks so that no single list dominates.
RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
    """Merges ranked lists; a chunk ranked well in several lists rises to the top."""
    scores: defaultdict[int, float] = defaultdict(float)
    chunks: dict[int, RetrievedChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.chunk_id] += 1 / (RRF_K + rank)
            chunks.setdefault(chunk.chunk_id, chunk)
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [replace(chunks[chunk_id], score=scores[chunk_id]) for chunk_id in ordered]
