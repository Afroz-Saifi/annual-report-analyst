from decimal import Decimal

from app.core.numbers import numbers_in
from app.evaluation.dataset import EvalQuestion
from app.evaluation.scoring import contains_accepted_answer


def number_question(*accepted: str) -> EvalQuestion:
    return EvalQuestion(id="q", category="c", question="?", type="number", accepted=list(accepted))


def text_question(*accepted: str) -> EvalQuestion:
    return EvalQuestion(id="q", category="c", question="?", type="text", accepted=list(accepted))


def test_numbers_in_reads_indian_grouping_and_decimals() -> None:
    assert numbers_in("Revenue was ₹1,78,650 crore and EPS 71.58.") == {
        Decimal("178650"),
        Decimal("71.58"),
    }


def test_numbers_in_ignores_citation_markers() -> None:
    assert numbers_in("The dividend was ₹48.00 [2][5].") == {Decimal("48")}


def test_number_matches_regardless_of_grouping_or_trailing_zeros() -> None:
    assert contains_accepted_answer(number_question("48"), "A total of ₹48.00 per share [1].")
    assert contains_accepted_answer(number_question("1,78,650"), "Revenue: 178650 crore.")


def test_number_does_not_match_inside_a_longer_number() -> None:
    assert not contains_accepted_answer(number_question("48"), "Total assets were 1,48,903.")
    assert not contains_accepted_answer(number_question("14.1"), "It was 114.1 or 14.15.")


def test_number_question_accepts_any_listed_form() -> None:
    assert contains_accepted_answer(number_question("12.6", "12.60"), "Attrition was 12.6%.")
    assert not contains_accepted_answer(number_question("12.6"), "Attrition was 14.1%.")


def test_text_matches_ignoring_case_and_spacing() -> None:
    question = text_question("June 23, 2026", "23 June 2026")

    assert contains_accepted_answer(question, "The AGM is on  june 23,\n2026 [1].")
    assert contains_accepted_answer(question, "It will be held on 23 June 2026.")
    assert not contains_accepted_answer(question, "It will be held on June 25, 2026.")
