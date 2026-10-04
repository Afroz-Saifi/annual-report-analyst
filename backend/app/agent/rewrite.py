from typing import Protocol

from google.genai.errors import APIError
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from pydantic import BaseModel, Field, SecretStr

from app.qa.baseline import AnswerGenerationError

SYSTEM_PROMPT = """A search over company annual reports failed to find the page that answers \
a question. Write new search queries that are more likely to match that page.

Guidelines:
- Name the statement or section that would hold the answer, for example \
"Consolidated Balance Sheet", "Consolidated Statement of Cash Flows", \
"Board's report" or "Business Responsibility and Sustainability Report".
- Use the line-item wording an annual report would print, not the question's wording.
- Keep each query short: a section name and a few key terms.
- Do not repeat a query that was already tried."""

PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "Question: {question}\n\nAlready tried:\n{tried}")]
)


class RewrittenQueries(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3, description="New search queries.")


class QueryRewriter(Protocol):
    async def rewrite(self, question: str, tried: list[str]) -> list[str]: ...


class GeminiQueryRewriter:
    def __init__(self, model: str, api_key: SecretStr) -> None:
        llm = ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=0)
        self._chain = PROMPT | llm.with_structured_output(RewrittenQueries)

    async def rewrite(self, question: str, tried: list[str]) -> list[str]:
        try:
            result = await self._chain.ainvoke(
                {"question": question, "tried": "\n".join(f"- {query}" for query in tried)}
            )
        except (ChatGoogleGenerativeAIError, APIError) as exc:
            raise AnswerGenerationError(str(exc)) from exc
        if not isinstance(result, RewrittenQueries):
            raise AnswerGenerationError("The model returned queries in an unexpected shape.")
        return result.queries
