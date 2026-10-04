from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Report
from tests.fakes import axis_vector


async def seed_report(session: AsyncSession) -> None:
    """Three chunks on three pages, each embedded on its own axis."""
    contents = [
        (1, "text", "Revenue from operations grew this year."),
        (2, "table", "Voluntary attrition for permanent employees fell."),
        (3, "text", "The Board recommended a final dividend."),
    ]
    session.add(
        Report(
            company="Sample Ltd",
            ticker="SAMPLE",
            fiscal_year=2025,
            source_url="https://example.com/sample.pdf",
            file_sha256="0" * 64,
            page_count=3,
            chunks=[
                Chunk(
                    page_number=page,
                    chunk_index=index,
                    kind=kind,
                    content=content,
                    embedding=axis_vector(index),
                )
                for index, (page, kind, content) in enumerate(contents)
            ],
        )
    )
    await session.commit()
