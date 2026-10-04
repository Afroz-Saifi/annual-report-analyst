import json
from collections.abc import AsyncIterator

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import AgentPipeline, build_agent
from app.api.deps import get_pipeline, get_session
from app.main import app
from app.qa.baseline import BaselinePipeline, DraftAnswer
from app.retrieval.retriever import VectorRetriever
from tests.fakes import AxisEmbeddings, FakeAnswerGenerator, FakeQueryRewriter
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
            "report_id": 1,
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


def use_agent(generator: FakeAnswerGenerator, rewriter: FakeQueryRewriter) -> None:
    retriever = VectorRetriever(AxisEmbeddings(query_axis=1))
    agent = AgentPipeline(build_agent(retriever, generator, rewriter, max_rewrites=1))
    app.dependency_overrides[get_pipeline] = lambda: agent


def parse_events(body: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


async def test_ask_stream_sends_each_step_and_then_the_answer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_report(db_session)
    draft = DraftAnswer(answer="Attrition fell [1].", citations=[1], found=True)
    use_agent(FakeAnswerGenerator(draft), FakeQueryRewriter())

    response = await client.post("/ask/stream", json={"question": "What was attrition?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_events(response.text)
    assert [name for name, _ in events] == ["step", "step", "step", "step", "answer"]
    assert [data["step"] for name, data in events if name == "step"] == [
        "scope",
        "retrieve",
        "answer",
        "verify",
    ]
    answer = events[-1][1]
    assert (answer["answer"], answer["verified"]) == ("Attrition fell [1].", True)


async def test_ask_stream_reports_a_model_failure_as_an_error_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_report(db_session)
    use_agent(FakeAnswerGenerator(draft=None), FakeQueryRewriter())

    response = await client.post("/ask/stream", json={"question": "What was attrition?"})

    assert response.status_code == 200
    events = parse_events(response.text)
    assert events[-1] == ("error", {"detail": "The language model request failed."})
    assert [data["step"] for _, data in events[:-1]] == ["scope", "retrieve"]
