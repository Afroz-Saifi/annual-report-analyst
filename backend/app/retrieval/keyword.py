from sqlalchemy import Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from app.retrieval.types import RetrievedChunk, to_retrieved


async def search_by_keywords(
    session: AsyncSession, question: str, limit: int
) -> list[RetrievedChunk]:
    """Returns the chunks sharing the most words with the question, best first."""
    # plainto_tsquery joins the words with AND, which no single chunk satisfies
    # for a full-sentence question. Rejoining with OR lets the rank decide.
    all_words = func.plainto_tsquery("english", question)
    any_word = cast(func.replace(cast(all_words, Text), "&", "|"), TSQUERY)
    rank = func.ts_rank_cd(Chunk.search_vector, any_word, 1).label("score")
    rows = await session.execute(
        select(Chunk, Report, rank)
        .join(Chunk.report)
        .where(Chunk.search_vector.bool_op("@@")(any_word))
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )
    return [to_retrieved(chunk, report, float(score)) for chunk, report, score in rows]
