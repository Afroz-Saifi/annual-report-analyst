from pydantic import BaseModel


class ReportSummary(BaseModel):
    id: int
    company: str
    ticker: str
    fiscal_year: int
    page_count: int
    has_pdf: bool
