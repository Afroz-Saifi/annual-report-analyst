from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.db.models import Report
from app.schemas.reports import ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


def pdf_path(report: Report) -> Path | None:
    if report.file_name is None:
        return None
    # Only the name is used, so a stored value can never point outside the folder.
    path = get_settings().raw_dir / Path(report.file_name).name
    return path if path.is_file() else None


@router.get("")
async def list_reports(session: SessionDep) -> list[ReportSummary]:
    reports = await session.scalars(select(Report).order_by(Report.company, Report.fiscal_year))
    return [
        ReportSummary(
            id=report.id,
            company=report.company,
            ticker=report.ticker,
            fiscal_year=report.fiscal_year,
            page_count=report.page_count,
            has_pdf=pdf_path(report) is not None,
        )
        for report in reports
    ]


@router.get("/{report_id}/pdf")
async def report_pdf(report_id: int, session: SessionDep) -> FileResponse:
    report = await session.get(Report, report_id)
    path = pdf_path(report) if report is not None else None
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No PDF is stored for this report.")
    return FileResponse(path, media_type="application/pdf")
