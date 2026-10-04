from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.dataset import EvalDataset, EvalQuestion, load_dataset

EVALS = Path(__file__).parents[2] / "evals"


@pytest.mark.parametrize("name", ["questions.yaml", "heldout.yaml"])
def test_the_committed_question_sets_load(name: str) -> None:
    dataset = load_dataset(EVALS / name)

    assert len(dataset.questions) >= 15
    assert any(not question.answerable for question in dataset.questions)
    assert all(question.page for question in dataset.questions if question.answerable)


def test_the_two_question_sets_share_no_questions() -> None:
    tuned = {q.question for q in load_dataset(EVALS / "questions.yaml").questions}
    held_out = {q.question for q in load_dataset(EVALS / "heldout.yaml").questions}

    assert tuned.isdisjoint(held_out)


def test_an_answerable_question_needs_an_accepted_answer() -> None:
    with pytest.raises(ValidationError, match="needs at least one accepted answer"):
        EvalQuestion(id="q", category="c", question="?")


def test_duplicate_ids_are_rejected() -> None:
    question = EvalQuestion(id="same", category="c", question="?", accepted=["1"])

    with pytest.raises(ValidationError, match="duplicate question ids"):
        EvalDataset(questions=[question, question])
