"""Plain retrieve-then-answer question answering.

One retrieval, one model call, no retries. This is what the evaluation
measures before the agent is added.
"""

from typing import Protocol

from google.genai.errors import APIError
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.retriever import Retriever
from app.retrieval.types import RetrievedChunk
from app.schemas.ask import AskResponse, Citation

EXCERPT_CHARS = 300

SYSTEM_PROMPT = """You answer questions about company annual reports.

Rules:
- Use only the numbered sources below. Do not use outside knowledge.
- After each claim, cite the sources that support it, like [1] or [2][5].
- Copy figures exactly as written in the source, with their units.
- If the sources do not contain the answer, say so plainly and cite nothing.
- Report what the documents say. Do not give investment advice."""

PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "Sources:\n{sources}\n\nQuestion: {question}")]
)


class DraftAnswer(BaseModel):
    answer: str = Field(description="The answer, with [n] citations after each claim.")
    citations: list[int] = Field(description="Numbers of the sources the answer relies on.")


class AnswerGenerationError(Exception):
    """The language model could not produce an answer."""


class AnswerGenerator(Protocol):
    async def generate(self, question: str, sources: list[RetrievedChunk]) -> DraftAnswer: ...


class GeminiAnswerGenerator:
    def __init__(self, model: str, api_key: SecretStr) -> None:
        llm = ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=0)
        self._chain = PROMPT | llm.with_structured_output(DraftAnswer)

    async def generate(self, question: str, sources: list[RetrievedChunk]) -> DraftAnswer:
        try:
            draft = await self._chain.ainvoke(
                {"sources": format_sources(sources), "question": question}
            )
        except (ChatGoogleGenerativeAIError, APIError) as exc:
            raise AnswerGenerationError(str(exc)) from exc
        if not isinstance(draft, DraftAnswer):
            raise AnswerGenerationError("The model returned an answer in an unexpected shape.")
        return draft


def format_sources(sources: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{number}] {source.company} annual report FY{source.fiscal_year}, "
        f"page {source.page_number} ({source.kind})\n{source.content}"
        for number, source in enumerate(sources, start=1)
    )


def build_response(draft: DraftAnswer, sources: list[RetrievedChunk]) -> AskResponse:
    # The model chooses the citation numbers, so drop any that are out of range or repeated.
    cited = sorted({number for number in draft.citations if 1 <= number <= len(sources)})
    return AskResponse(
        answer=draft.answer,
        citations=[
            Citation(
                source=number,
                company=sources[number - 1].company,
                fiscal_year=sources[number - 1].fiscal_year,
                page_number=sources[number - 1].page_number,
                kind=sources[number - 1].kind,
                source_url=sources[number - 1].source_url,
                excerpt=sources[number - 1].content[:EXCERPT_CHARS],
            )
            for number in cited
        ],
    )


async def retrieve_and_answer(
    session: AsyncSession,
    retriever: Retriever,
    generator: AnswerGenerator,
    question: str,
    top_k: int,
) -> tuple[AskResponse, list[RetrievedChunk]]:
    """Answers the question and also returns every source the model was shown."""
    sources = await retriever.retrieve(session, question, limit=top_k)
    if not sources:
        return AskResponse(answer="No reports have been ingested yet.", citations=[]), []
    draft = await generator.generate(question, sources)
    return build_response(draft, sources), sources


async def answer_question(
    session: AsyncSession,
    retriever: Retriever,
    generator: AnswerGenerator,
    question: str,
    top_k: int,
) -> AskResponse:
    response, _ = await retrieve_and_answer(session, retriever, generator, question, top_k)
    return response
