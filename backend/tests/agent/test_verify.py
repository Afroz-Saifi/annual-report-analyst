from app.agent.verify import unsupported_figures
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
