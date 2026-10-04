from app.retrieval.fusion import RRF_K, reciprocal_rank_fusion
from app.retrieval.types import RetrievedChunk


def chunk(chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        report_id=1,
        company="Sample Ltd",
        fiscal_year=2025,
        source_url="https://example.com/sample.pdf",
        page_number=chunk_id,
        kind="text",
        content=f"chunk {chunk_id}",
        score=0.0,
    )


def test_a_chunk_ranked_well_in_both_lists_beats_one_that_tops_a_single_list() -> None:
    by_meaning = [chunk(1), chunk(2), chunk(3)]
    by_keywords = [chunk(4), chunk(2), chunk(5)]

    fused = reciprocal_rank_fusion([by_meaning, by_keywords])

    assert [c.chunk_id for c in fused][:3] == [2, 1, 4]


def test_fused_score_is_the_sum_of_reciprocal_ranks() -> None:
    fused = reciprocal_rank_fusion([[chunk(1), chunk(2)], [chunk(2)]])

    scores = {c.chunk_id: c.score for c in fused}
    assert scores[2] == 1 / (RRF_K + 2) + 1 / (RRF_K + 1)
    assert scores[1] == 1 / (RRF_K + 1)


def test_each_chunk_appears_once() -> None:
    fused = reciprocal_rank_fusion([[chunk(1), chunk(2)], [chunk(2), chunk(1)]])

    assert sorted(c.chunk_id for c in fused) == [1, 2]


def test_no_rankings_gives_no_results() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
