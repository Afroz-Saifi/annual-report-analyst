from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.main import app


class FakeSession:
    def __init__(self, result: str | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def scalar(self, _statement: object) -> str | None:
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_session(session: FakeSession) -> None:
    async def override() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_session] = override


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_pgvector_version(client: TestClient) -> None:
    use_session(FakeSession(result="0.8.0"))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "pgvector_version": "0.8.0"}


def test_ready_fails_when_database_is_unreachable(client: TestClient) -> None:
    use_session(FakeSession(error=ConnectionRefusedError()))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unreachable."}


def test_ready_fails_when_pgvector_is_missing(client: TestClient) -> None:
    use_session(FakeSession(result=None))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "The pgvector extension is not installed."}
