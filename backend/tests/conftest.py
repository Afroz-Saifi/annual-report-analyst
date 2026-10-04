from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fpdf import FPDF
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base

TEST_DATABASE = "analyst_test"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)

    pdf.add_page()
    pdf.multi_cell(0, 6, "Chairman's letter. Revenue grew steadily across all regions this year.")

    pdf.add_page()
    pdf.multi_cell(0, 6, "Employee metrics for the last two years.")
    pdf.ln(4)
    with pdf.table() as table:
        for cells in (("Metric", "FY24", "FY25"), ("Headcount", "1,000", "1,200")):
            row = table.row()
            for cell in cells:
                row.cell(cell)

    path = tmp_path / "sample-report.pdf"
    pdf.output(str(path))
    return path


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session on a throwaway database; skips the test when PostgreSQL is not running."""
    admin_url = make_url(get_settings().database_url)
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE}"))
            await connection.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
    except (SQLAlchemyError, OSError):
        await admin.dispose()
        pytest.skip("PostgreSQL is not running")

    engine = create_async_engine(admin_url.set(database=TEST_DATABASE))
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session

    await engine.dispose()
    async with admin.connect() as connection:
        await connection.execute(text(f"DROP DATABASE {TEST_DATABASE}"))
    await admin.dispose()
