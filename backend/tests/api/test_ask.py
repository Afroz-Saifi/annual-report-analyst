from collections.abc import AsyncIterator

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_pipeline, get_session
from app.main import app
from app.qa.baseline import BaselinePipeline, DraftAnswer
from app.retrieval.retriever import VectorRetriever
from tests.fakes import AxisEmbeddings, FakeAnswerGenerator
from tests.retrieval.seed import seed_report

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def use_generator(generator: FakeAnswerGenerator) -> None:
    pipeline = BaselinePipeline(VectorRetriever(AxisEmbeddings(query_axis=1)), generator)
    app.dependency_overrides[get_pipeline] = lambda: pipeline


async def test_ask_answers_with_citations_from_the_retrieved_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_report(db_session)
    generator = FakeAnswerGenerator(
        DraftAnswer(answer="Attrition fell [1].", citations=[1], found=True)
    )
    use_generator(generator)

    response = await client.post("/ask", json={"question": "What was attrition?", "top_k": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Attrition fell [1]."
    assert body["citations"] == [
        {
            "source": 1,
            "company": "Sample Ltd",
            "fiscal_year": 2025,
            "page_number": 2,
            "kind": "table",
            "source_url": "https://example.com/sample.pdf",
            "excerpt": "Voluntary attrition for permanent employees fell.",
        }
    ]
    assert len(generator.calls[0]) == 2


async def test_ask_without_ingested_reports_says_so_and_skips_the_model(
    client: AsyncClient,
) -> None:
    generator = FakeAnswerGenerator(DraftAnswer(answer="unused", citations=[], found=True))
    use_generator(generator)

    response = await client.post("/ask", json={"question": "What was attrition?"})

    assert response.status_code == 200
    body = response.json()
    assert (body["answer"], body["citations"]) == ("No reports have been ingested yet.", [])
    assert generator.calls == []


async def test_ask_returns_502_when_the_model_fails(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_report(db_session)
    use_generator(FakeAnswerGenerator(draft=None))

    response = await client.post("/ask", json={"question": "What was attrition?"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The language model request failed."}


async def test_ask_rejects_a_too_short_question(client: AsyncClient) -> None:
    use_generator(FakeAnswerGenerator(draft=None))

    response = await client.post("/ask", json={"question": "a"})

    assert response.status_code == 422
