from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from domain.value_objects import EnrichOperation, EnrichResult, NodeEnrichment
from main import app


class _FakeEnrichRunner:
    def __init__(
        self,
        *,
        available: bool = True,
        result: EnrichResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._available = available
        self._result = result
        self._raises = raises
        self.last_call: dict | None = None

    @property
    def is_available(self) -> bool:
        return self._available

    async def run(
        self,
        *,
        document_json: str,
        operations: list[EnrichOperation],
        model_id: str | None = None,
    ) -> EnrichResult:
        self.last_call = {
            "document_json": document_json,
            "operations": operations,
            "model_id": model_id,
        }
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


@pytest.fixture(autouse=True)
def _clear_runner():
    old = getattr(app.state, "enrich_runner", None)
    yield
    app.state.enrich_runner = old


def test_503_when_runner_not_wired() -> None:
    app.state.enrich_runner = None
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={"documentJson": "{}", "operations": ["summarize"]},
    )
    assert r.status_code == 503


def test_400_when_document_json_empty() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(
        result=EnrichResult(document_json="{}", enrichments=[], operations=[])
    )
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={"documentJson": "   ", "operations": ["summarize"]},
    )
    assert r.status_code == 400


def test_400_when_operations_empty() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(
        result=EnrichResult(document_json="{}", enrichments=[], operations=[])
    )
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={"documentJson": "{}", "operations": []},
    )
    assert r.status_code == 400


def test_400_when_operation_name_unknown() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(
        result=EnrichResult(document_json="{}", enrichments=[], operations=[])
    )
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={"documentJson": "{}", "operations": ["sumarize"]},  # typo
    )
    assert r.status_code == 400
    assert "sumarize" in r.json()["detail"]


def test_operations_deduplicated_in_order() -> None:
    fake = _FakeEnrichRunner(
        result=EnrichResult(
            document_json='{"body": {}}',
            enrichments=[],
            operations=[EnrichOperation.SUMMARIZE, EnrichOperation.KEYWORDS],
        )
    )
    app.state.enrich_runner = fake
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={
            "documentJson": "{}",
            "operations": ["summarize", "keywords", "summarize"],
        },
    )
    assert r.status_code == 200
    # The runner sees the de-duplicated, in-order list.
    assert fake.last_call is not None
    assert fake.last_call["operations"] == [
        EnrichOperation.SUMMARIZE,
        EnrichOperation.KEYWORDS,
    ]


def test_500_when_runner_raises() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(raises=RuntimeError("ollama down"))
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={"documentJson": "{}", "operations": ["summarize"]},
    )
    assert r.status_code == 500
    assert "ollama down" in r.json()["detail"]


def test_happy_path_serializes_enrichments() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(
        result=EnrichResult(
            document_json='{"body": {"children": []}}',
            enrichments=[
                NodeEnrichment(
                    self_ref="#/texts/0",
                    operation=EnrichOperation.SUMMARIZE,
                    value="The doc introduces docling.",
                ),
                NodeEnrichment(
                    self_ref="#/texts/0",
                    operation=EnrichOperation.KEYWORDS,
                    value=["docling", "pdf", "parser"],
                ),
                NodeEnrichment(
                    self_ref="#/texts/0",
                    operation=EnrichOperation.ENTITIES,
                    value=[
                        {"entity_type": "ORG", "mention": "IBM"},
                        {"entity_type": "PRODUCT", "mention": "Granite"},
                    ],
                ),
            ],
            operations=[
                EnrichOperation.SUMMARIZE,
                EnrichOperation.KEYWORDS,
                EnrichOperation.ENTITIES,
            ],
        )
    )
    client = TestClient(app)
    r = client.post(
        "/api/enrich",
        json={
            "documentJson": "{}",
            "operations": ["summarize", "keywords", "entities"],
            "modelId": "mistral-small3.2",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["documentJson"] == '{"body": {"children": []}}'
    assert body["operations"] == ["summarize", "keywords", "entities"]
    assert body["modelId"] == "mistral-small3.2"
    # camelCase via to_camel alias generator.
    enrichments = body["enrichments"]
    assert len(enrichments) == 3
    assert enrichments[0]["selfRef"] == "#/texts/0"
    assert enrichments[0]["operation"] == "summarize"
    assert enrichments[0]["value"] == "The doc introduces docling."
    assert enrichments[1]["value"] == ["docling", "pdf", "parser"]
    assert enrichments[2]["operation"] == "entities"
    # Entities come through as list[{entity_type, mention}] verbatim.
    assert enrichments[2]["value"] == [
        {"entity_type": "ORG", "mention": "IBM"},
        {"entity_type": "PRODUCT", "mention": "Granite"},
    ]


def test_health_reports_enrich_availability() -> None:
    app.state.enrich_runner = _FakeEnrichRunner(
        available=True,
        result=EnrichResult(document_json="{}", enrichments=[], operations=[]),
    )
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["enrichAvailable"] is True
