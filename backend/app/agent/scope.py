import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KnownReport:
    id: int
    company: str
    ticker: str
    fiscal_year: int


@dataclass(frozen=True)
class CompanyScope:
    company: str
    report_ids: list[int]


@dataclass(frozen=True)
class SearchScope:
    label: str
    report_ids: list[int]


_YEAR_PATTERNS = [
    re.compile(r"\bfiscal (?:year )?(20\d\d)\b", re.IGNORECASE),
    re.compile(r"\bFY ?(20\d\d)\b", re.IGNORECASE),
    re.compile(r"\bFY ?(\d\d)\b", re.IGNORECASE),
    re.compile(r"\b20\d\d-(\d\d)\b"),
    re.compile(r"\bMarch 31, (20\d\d)\b", re.IGNORECASE),
]


def companies_named_in(question: str, reports: list[KnownReport]) -> list[CompanyScope]:
    """The companies the question names, by name or ticker, in the order it names them."""
    by_company: dict[str, list[int]] = {}
    first_mention: dict[str, int] = {}
    for report in reports:
        mentions = [
            match.start()
            for alias in (report.company, report.ticker)
            for match in re.finditer(rf"\b{re.escape(alias)}\b", question, re.IGNORECASE)
        ]
        if mentions:
            by_company.setdefault(report.company, []).append(report.id)
            first_mention[report.company] = min(
                first_mention.get(report.company, len(question)), *mentions
            )
    ordered = sorted(by_company, key=lambda company: first_mention[company])
    return [CompanyScope(company, sorted(by_company[company])) for company in ordered]


def fiscal_years_named_in(question: str) -> set[int]:
    """Fiscal years written as "fiscal 2026", "FY2026", "FY26", "2025-26" or "March 31, 2026"."""
    years = set()
    for pattern in _YEAR_PATTERNS:
        for match in pattern.finditer(question):
            year = int(match.group(1))
            years.add(year if year > 100 else 2000 + year)
    return years


def plan_search(question: str, reports: list[KnownReport]) -> list[SearchScope]:
    """How to split the search: one scope per company named, and per year when two are named.

    An empty plan means searching every report together.
    """
    companies = companies_named_in(question, reports)
    groups = [(scope.company, set(scope.report_ids)) for scope in companies] or [
        ("", {report.id for report in reports})
    ]
    years = fiscal_years_named_in(question)
    by_id = {report.id: report for report in reports}

    plan: list[SearchScope] = []
    for company, ids in groups:
        # A report also covers earlier years in its comparatives, so years only
        # split the search when the question compares two years that each have
        # their own report; one year alone never narrows it.
        reports_per_year = {
            year: sorted(i for i in ids if by_id[i].fiscal_year == year) for year in years
        }
        matched = {year: ids_ for year, ids_ in reports_per_year.items() if ids_}
        if len(matched) >= 2:
            for year in sorted(matched, reverse=True):
                label = f"{company or by_id[matched[year][0]].company} FY{year}"
                plan.append(SearchScope(label, matched[year]))
        elif company:
            plan.append(SearchScope(company, sorted(ids)))
    return plan
