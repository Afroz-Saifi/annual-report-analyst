from app.qa.baseline import EXCERPT_CHARS, DraftAnswer, build_response, format_sources
from app.retrieval.vector import RetrievedChunk


def source(page: int, content: str, kind: str = "text") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=page,
        company="Infosys",
        fiscal_year=2026,
        source_url="https://example.com/ar.pdf",
        page_number=page,
        kind=kind,
        content=content,
        distance=0.1,
    )


def test_format_sources_numbers_each_source_with_its_report_and_page() -> None:
    text = format_sources([source(36, "Dividend of 25 per share."), source(144, "| a |", "table")])

    assert text == (
        "[1] Infosys annual report FY2026, page 36 (text)\nDividend of 25 per share.\n\n"
        "[2] Infosys annual report FY2026, page 144 (table)\n| a |"
    )


def test_build_response_maps_citation_numbers_to_their_sources() -> None:
    sources = [source(36, "Dividend of 25 per share."), source(209, "Revenue from operations.")]
    draft = DraftAnswer(answer="The dividend was 25 per share [1].", citations=[1])

    response = build_response(draft, sources)

    assert response.answer == "The dividend was 25 per share [1]."
    assert [(c.source, c.page_number, c.excerpt) for c in response.citations] == [
        (1, 36, "Dividend of 25 per share.")
    ]


def test_build_response_drops_out_of_range_and_repeated_citations() -> None:
    sources = [source(36, "a"), source(209, "b")]
    draft = DraftAnswer(answer="x [2][2][7]", citations=[2, 2, 7, 0, -1])

    response = build_response(draft, sources)

    assert [c.source for c in response.citations] == [2]


def test_build_response_shortens_long_excerpts() -> None:
    draft = DraftAnswer(answer="x [1]", citations=[1])

    response = build_response(draft, [source(1, "y" * 1000)])

    assert len(response.citations[0].excerpt) == EXCERPT_CHARS
