from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from domain.ports import ReasoningParseError
from domain.value_objects import ReasoningIteration, ReasoningResult
from main import app


class _FakeRunner:
    def __init__(
        self,
        *,
        available: bool = True,
        result: ReasoningResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._available = available
        self._result = result
        self._raises = raises

    @property
    def is_available(self) -> bool:
        return self._available

    async def run(self, *, document_json: str, query: str, model_id: str | None = None):
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


@pytest.fixture(autouse=True)
def _clear_runner():
    old = getattr(app.state, "reasoning_runner", None)
    yield
    app.state.reasoning_runner = old


def test_503_when_runner_not_wired() -> None:
    app.state.reasoning_runner = None
    client = TestClient(app)
    r = client.post("/api/reasoning", json={"documentJson": "{}", "query": "q"})
    assert r.status_code == 503


def test_400_when_query_empty() -> None:
    app.state.reasoning_runner = _FakeRunner(
        result=ReasoningResult(answer="", iterations=[], converged=False)
    )
    client = TestClient(app)
    r = client.post("/api/reasoning", json={"documentJson": "{}", "query": "   "})
    assert r.status_code == 400


def test_400_when_document_json_empty() -> None:
    app.state.reasoning_runner = _FakeRunner(
        result=ReasoningResult(answer="", iterations=[], converged=False)
    )
    client = TestClient(app)
    r = client.post("/api/reasoning", json={"documentJson": "", "query": "q"})
    assert r.status_code == 400


def test_502_on_parse_error() -> None:
    app.state.reasoning_runner = _FakeRunner(
        raises=ReasoningParseError(model_id="m", reason="no parseable answer")
    )
    client = TestClient(app)
    r = client.post("/api/reasoning", json={"documentJson": "{}", "query": "q"})
    assert r.status_code == 502
    assert "couldn't produce a parseable" in r.json()["detail"]


def test_happy_path_returns_trace() -> None:
    app.state.reasoning_runner = _FakeRunner(
        result=ReasoningResult(
            answer="2.45 pages/sec",
            converged=True,
            iterations=[
                ReasoningIteration(
                    iteration=1,
                    section_ref="#/texts/12",
                    reason="found table",
                    section_text_length=180,
                    can_answer=True,
                    response="M3 Max default = 2.45",
                ),
            ],
        )
    )
    client = TestClient(app)
    r = client.post(
        "/api/reasoning",
        json={"documentJson": "{}", "query": "throughput?", "modelId": "mistral"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "2.45 pages/sec"
    assert body["converged"] is True
    assert len(body["steps"]) == 1
    assert body["steps"][0]["kind"] == "read"
    assert body["steps"][0]["citations"] == ["#/texts/12"]
    assert body["modelId"] == "mistral"


def test_health_reports_reasoning_availability() -> None:
    app.state.reasoning_runner = _FakeRunner(
        available=True, result=ReasoningResult(answer="", iterations=[], converged=False)
    )
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["reasoningAvailable"] is True
