from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.db.models import Report
from app.main import app
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(get_settings(), "raw_dir", tmp_path)
    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def store_pdf(session: AsyncSession, folder: Path, file_name: str) -> None:
    (folder / "sample.pdf").write_bytes(b"%PDF-1.4 sample")
    report = (await session.scalars(select(Report))).one()
    report.file_name = file_name
    await session.commit()


async def test_reports_are_listed_with_whether_their_pdf_is_available(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    await seed_report(db_session)

    before = (await client.get("/reports")).json()
    await store_pdf(db_session, tmp_path, "sample.pdf")
    after = (await client.get("/reports")).json()

    assert before == [
        {
            "id": 1,
            "company": "Sample Ltd",
            "ticker": "SAMPLE",
            "fiscal_year": 2025,
            "page_count": 3,
            "has_pdf": False,
        }
    ]
    assert after[0]["has_pdf"] is True


async def test_the_pdf_of_a_report_is_served(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    await seed_report(db_session)
    await store_pdf(db_session, tmp_path, "sample.pdf")

    response = await client.get("/reports/1/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 sample"


async def test_a_stored_file_name_cannot_reach_outside_the_reports_folder(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Path
) -> None:
    await seed_report(db_session)
    await store_pdf(db_session, tmp_path, "../../sample.pdf")

    response = await client.get("/reports/1/pdf")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 sample"


async def test_a_missing_pdf_or_unknown_report_is_a_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_report(db_session)

    assert (await client.get("/reports/1/pdf")).status_code == 404
    assert (await client.get("/reports/999/pdf")).status_code == 404
