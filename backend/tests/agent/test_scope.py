import pytest

from app.agent.scope import (
    CompanyScope,
    KnownReport,
    SearchScope,
    companies_named_in,
    fiscal_years_named_in,
    plan_search,
)

REPORTS = [
    KnownReport(id=1, company="Infosys", ticker="INFY", fiscal_year=2026),
    KnownReport(id=2, company="Infosys", ticker="INFY", fiscal_year=2025),
    KnownReport(id=3, company="Tata Consultancy Services", ticker="TCS", fiscal_year=2026),
]


def test_a_company_is_found_by_name_or_ticker_with_all_its_reports() -> None:
    assert companies_named_in("What was Infosys's revenue?", REPORTS) == [
        CompanyScope("Infosys", [1, 2])
    ]
    assert companies_named_in("What was INFY's revenue?", REPORTS) == [
        CompanyScope("Infosys", [1, 2])
    ]


def test_companies_are_listed_in_the_order_the_question_names_them() -> None:
    named = companies_named_in("Compare TCS and Infosys attrition", REPORTS)

    assert [scope.company for scope in named] == ["Tata Consultancy Services", "Infosys"]


def test_matching_ignores_case_but_needs_a_whole_word() -> None:
    assert companies_named_in("compare tcs with infosys", REPORTS) != []
    assert companies_named_in("What is TCSL or Infosystems?", REPORTS) == []


def test_a_question_naming_no_known_company_gives_no_scope() -> None:
    assert companies_named_in("What was Wipro's revenue?", REPORTS) == []


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("in fiscal 2026 and fiscal year 2025", {2026, 2025}),
        ("FY2026 versus FY 25", {2026, 2025}),
        ("the 2025-26 report", {2026}),
        ("as at March 31, 2025", {2025}),
        ("in Q2 or FY or 2026 alone", set()),
    ],
)
def test_fiscal_years_are_read_in_their_usual_forms(text: str, years: set[int]) -> None:
    assert fiscal_years_named_in(text) == years


def test_two_years_for_one_company_split_the_search_by_report() -> None:
    plan = plan_search("Infosys headcount in fiscal 2026 and fiscal 2025?", REPORTS)

    assert plan == [SearchScope("Infosys FY2026", [1]), SearchScope("Infosys FY2025", [2])]


def test_one_year_does_not_narrow_the_search() -> None:
    assert plan_search("Infosys revenue in fiscal 2025?", REPORTS) == [
        SearchScope("Infosys", [1, 2])
    ]


def test_a_year_without_its_own_report_does_not_split_the_search() -> None:
    assert plan_search("Infosys profit in fiscal 2026 and fiscal 2024?", REPORTS) == [
        SearchScope("Infosys", [1, 2])
    ]


def test_two_years_and_no_company_split_every_report_by_year() -> None:
    plan = plan_search("Revenue in fiscal 2026 versus fiscal 2025?", REPORTS)

    assert [scope.report_ids for scope in plan] == [[1, 3], [2]]


def test_no_company_and_no_years_searches_everything_together() -> None:
    assert plan_search("What was revenue?", REPORTS) == []
