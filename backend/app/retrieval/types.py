from dataclasses import dataclass

from app.db.models import Chunk, Report


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    report_id: int
    company: str
    fiscal_year: int
    source_url: str
    page_number: int
    kind: str
    content: str
    # Higher is better. The scale depends on the stage that produced the list:
    # cosine similarity, keyword rank, fused rank or reranker score.
    score: float


def to_retrieved(chunk: Chunk, report: Report, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        report_id=report.id,
        company=report.company,
        fiscal_year=report.fiscal_year,
        source_url=report.source_url,
        page_number=chunk.page_number,
        kind=chunk.kind,
        content=chunk.content,
        score=score,
    )
