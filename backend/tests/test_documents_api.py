from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


class _FakeConverter:
    def __init__(self, *, available: bool = True, raises: Exception | None = None) -> None:
        self._available = available
        self._raises = raises
        self.last_call: tuple[str, int] | None = None

    @property
    def is_available(self) -> bool:
        return self._available

    async def convert(self, *, filename: str, pdf_bytes: bytes) -> str:
        self.last_call = (filename, len(pdf_bytes))
        if self._raises is not None:
            raise self._raises
        return '{"name": "fake-doc"}'


@pytest.fixture(autouse=True)
def _restore_converter():
    old = getattr(app.state, "pdf_converter", None)
    yield
    app.state.pdf_converter = old


def test_503_when_converter_not_wired() -> None:
    app.state.pdf_converter = None
    client = TestClient(app)
    r = client.post(
        "/api/documents",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 503


def test_400_when_not_a_pdf() -> None:
    app.state.pdf_converter = _FakeConverter()
    client = TestClient(app)
    r = client.post(
        "/api/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_400_on_empty_upload() -> None:
    app.state.pdf_converter = _FakeConverter()
    client = TestClient(app)
    r = client.post(
        "/api/documents",
        files={"file": ("doc.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400


def test_500_when_converter_raises() -> None:
    app.state.pdf_converter = _FakeConverter(raises=RuntimeError("docling exploded"))
    client = TestClient(app)
    r = client.post(
        "/api/documents",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 500
    assert "docling exploded" in r.json()["detail"]


def test_happy_path_returns_document_json() -> None:
    fake = _FakeConverter()
    app.state.pdf_converter = fake
    client = TestClient(app)
    r = client.post(
        "/api/documents",
        files={"file": ("doc.pdf", b"%PDF-1.4 hello", "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "doc.pdf"
    assert body["documentJson"] == '{"name": "fake-doc"}'
    assert body["sizeBytes"] == len(b"%PDF-1.4 hello")
    assert fake.last_call == ("doc.pdf", len(b"%PDF-1.4 hello"))


def test_413_when_pdf_exceeds_max_size() -> None:
    # The upload limit lives on `app.state.max_pdf_size_mb` (published by
    # `main.py`), so the test sets it directly — no infra.settings mutation,
    # no frozen-dataclass hack.
    app.state.pdf_converter = _FakeConverter()
    previous = getattr(app.state, "max_pdf_size_mb", 25)
    app.state.max_pdf_size_mb = 1
    try:
        client = TestClient(app)
        r = client.post(
            "/api/documents",
            files={"file": ("big.pdf", b"x" * (2 * 1024 * 1024), "application/pdf")},
        )
        assert r.status_code == 413
    finally:
        app.state.max_pdf_size_mb = previous
