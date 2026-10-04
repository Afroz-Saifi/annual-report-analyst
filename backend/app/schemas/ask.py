from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=8, ge=1, le=20)


class Citation(BaseModel):
    source: int = Field(description="The number used for this source in the answer, as in [2].")
    company: str
    fiscal_year: int
    page_number: int
    kind: str
    source_url: str
    excerpt: str


class AgentStep(BaseModel):
    step: str
    detail: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    verified: bool | None = Field(
        default=None,
        description="True when every figure in the answer appears in a cited source. "
        "None when the answer was not checked.",
    )
    unverified_figures: list[str] = []
    steps: list[AgentStep] = []
