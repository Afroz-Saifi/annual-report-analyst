from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.dataset import EvalDataset, EvalQuestion, load_dataset

QUESTIONS_FILE = Path(__file__).parents[2] / "evals" / "questions.yaml"


def test_the_committed_question_set_loads() -> None:
    dataset = load_dataset(QUESTIONS_FILE)

    assert len(dataset.questions) >= 30
    assert any(not question.answerable for question in dataset.questions)
    assert all(question.page for question in dataset.questions if question.answerable)


def test_an_answerable_question_needs_an_accepted_answer() -> None:
    with pytest.raises(ValidationError, match="needs at least one accepted answer"):
        EvalQuestion(id="q", category="c", question="?")


def test_duplicate_ids_are_rejected() -> None:
    question = EvalQuestion(id="same", category="c", question="?", accepted=["1"])

    with pytest.raises(ValidationError, match="duplicate question ids"):
        EvalDataset(questions=[question, question])
