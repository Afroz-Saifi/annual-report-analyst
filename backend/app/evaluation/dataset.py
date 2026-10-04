from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, model_validator


class EvalQuestion(BaseModel):
    id: str
    category: str
    question: str
    answerable: bool = True
    type: Literal["number", "text"] = "number"
    accepted: list[str] = []
    page: int | None = None
    # A second page for answers drawn from two reports.
    other_page: int | None = None

    @model_validator(mode="after")
    def answerable_questions_need_an_accepted_answer(self) -> Self:
        if self.answerable and not self.accepted:
            raise ValueError(
                f"{self.id}: an answerable question needs at least one accepted answer"
            )
        return self


class EvalDataset(BaseModel):
    questions: list[EvalQuestion]

    @model_validator(mode="after")
    def ids_are_unique(self) -> Self:
        ids = [question.id for question in self.questions]
        duplicates = {id_ for id_ in ids if ids.count(id_) > 1}
        if duplicates:
            raise ValueError(f"duplicate question ids: {sorted(duplicates)}")
        return self


def load_dataset(path: Path) -> EvalDataset:
    return EvalDataset.model_validate(yaml.safe_load(path.read_text()))
