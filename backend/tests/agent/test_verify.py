from app.agent.verify import check_figures, unsupported_figures
from app.retrieval.types import RetrievedChunk


def source(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=1,
        report_id=1,
        company="Sample Ltd",
        fiscal_year=2026,
        source_url="https://example.com/sample.pdf",
        page_number=1,
        kind="text",
        content=content,
        score=1.0,
    )


def test_figures_found_in_a_cited_source_are_supported() -> None:
    cited = [source("Revenue from operations 2.18 1,78,650 1,62,990")]

    assert unsupported_figures("Revenue was ₹1,78,650 crore [1].", "What was revenue?", cited) == []


def test_a_figure_missing_from_the_cited_sources_is_reported_as_written() -> None:
    cited = [source("Revenue from operations 1,78,650")]

    answer = "Revenue was ₹1,78,650 crore, up 9.6% [1]."

    assert unsupported_figures(answer, "What was revenue?", cited) == ["9.6"]


def test_figures_repeated_from_the_question_are_not_reported() -> None:
    cited = [source("Number of large clients 88")]

    answer = "Infosys had 88 clients above US$50 million in fiscal 2026 [1]."
    question = "How many US$50 million clients were there in fiscal 2026?"

    assert unsupported_figures(answer, question, cited) == []


def test_the_same_figure_written_differently_still_matches() -> None:
    cited = [source("Total dividend 48.00")]

    assert unsupported_figures("The dividend was ₹48 per share [1].", "Dividend?", cited) == []


def test_each_unsupported_figure_is_listed_once() -> None:
    answer = "It rose 12.5% to 300, then another 12.5%."

    assert unsupported_figures(answer, "?", [source("no figures here")]) == ["12.5", "300"]


def test_labels_such_as_fy26_are_not_read_as_figures() -> None:
    assert unsupported_figures("Growth continued in FY26 and Q2.", "?", []) == []


def test_a_difference_of_two_stated_figures_is_accepted_and_explained() -> None:
    cited = [source("Total remuneration 82.60 in fiscal 2026"), source("Total 80.62 in 2025")]
    answer = "It rose from ₹80.62 crore to ₹82.60 crore, an increase of ₹1.98 crore [1][2]."

    check = check_figures(answer, "?", cited)

    assert check.unsupported == []
    assert check.derived == {"1.98": "1.98 = 82.60 - 80.62"}


def test_a_percentage_change_is_accepted_at_the_precision_written() -> None:
    cited = [source("Revenue 1,78,650 and 1,62,990")]
    answer = "Revenue grew from 1,62,990 to 1,78,650, or 9.6% [1]."

    assert check_figures(answer, "?", cited).derived == {
        "9.6": "9.6% = change from 1,62,990 to 1,78,650"
    }


def test_a_worked_figure_needs_both_operands_stated_in_the_answer() -> None:
    cited = [source("Total remuneration 82.60 and 80.62")]

    check = check_figures("It rose by ₹1.98 crore [1].", "?", cited)

    assert check.unsupported == ["1.98"]


def test_a_figure_that_is_no_sum_or_difference_is_still_unsupported() -> None:
    cited = [source("Values 100 and 40")]

    assert check_figures("From 100 to 40, a gap of 55 [1].", "?", cited).unsupported == ["55"]
