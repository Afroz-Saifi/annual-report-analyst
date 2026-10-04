from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.dataset import EvalDataset, EvalQuestion, load_dataset

EVALS = Path(__file__).parents[2] / "evals"


@pytest.mark.parametrize(
    "name",
    ["questions.yaml", "heldout.yaml", "comparison.yaml", "cross_company.yaml", "heldout_v2.yaml"],
)
def test_the_committed_question_sets_load(name: str) -> None:
    dataset = load_dataset(EVALS / name)

    assert len(dataset.questions) >= 8
    assert all(question.page for question in dataset.questions if question.answerable)


def test_no_question_appears_in_two_sets() -> None:
    names = ["questions", "heldout", "comparison", "cross_company", "heldout_v2"]
    questions = [
        q.question for name in names for q in load_dataset(EVALS / f"{name}.yaml").questions
    ]

    assert len(questions) == len(set(questions))


def test_an_answerable_question_needs_an_accepted_answer() -> None:
    with pytest.raises(ValidationError, match="needs at least one accepted answer"):
        EvalQuestion(id="q", category="c", question="?")


def test_duplicate_ids_are_rejected() -> None:
    question = EvalQuestion(id="same", category="c", question="?", accepted=["1"])

    with pytest.raises(ValidationError, match="duplicate question ids"):
        EvalDataset(questions=[question, question])
