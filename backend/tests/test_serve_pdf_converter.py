"""Contract tests for the docling-serve HTTP adapter.

Use an httpx MockTransport so we exercise the real client + multipart
encoding without standing up a docling-serve. The assertions pin down:
- endpoint path + method,
- `X-Api-Key` header,
- the `files` field + `to_formats=json` form key,
- the response parsing (dict json_content → string).
"""

from __future__ import annotations

import json

import httpx
import pytest

from infra.serve_pdf_converter import ServePdfConverter


def _patch_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_init = httpx.AsyncClient.__init__

    def _init(self, *args, **kwargs) -> None:
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _init)


async def test_convert_posts_pdf_and_returns_json_string(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["api_key"] = request.headers.get("X-Api-Key")
        captured["content_type"] = request.headers.get("Content-Type", "")
        # Body contains the multipart form — assert the expected fields show up.
        body = request.content.decode("latin-1", errors="ignore")
        captured["body"] = body
        return httpx.Response(
            200,
            json={
                "document": {
                    "json_content": {"name": "doc.pdf", "texts": []},
                }
            },
        )

    _patch_client(monkeypatch, handler)

    converter = ServePdfConverter(base_url="http://serve.example", api_key="s3cret")
    out = await converter.convert(filename="doc.pdf", pdf_bytes=b"%PDF-1.4 hi")

    assert json.loads(out) == {"name": "doc.pdf", "texts": []}
    assert captured["url"] == "http://serve.example/v1/convert/file"
    assert captured["method"] == "POST"
    assert captured["api_key"] == "s3cret"
    assert "multipart/form-data" in captured["content_type"]
    body = captured["body"]
    assert isinstance(body, str)
    assert "to_formats" in body and "json" in body
    assert "doc.pdf" in body


async def test_convert_raises_when_json_content_missing(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"document": {}})

    _patch_client(monkeypatch, handler)

    converter = ServePdfConverter(base_url="http://serve.example")
    with pytest.raises(RuntimeError, match="json_content"):
        await converter.convert(filename="x.pdf", pdf_bytes=b"%PDF")


async def test_convert_raises_for_status(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    _patch_client(monkeypatch, handler)

    converter = ServePdfConverter(base_url="http://serve.example")
    with pytest.raises(httpx.HTTPStatusError):
        await converter.convert(filename="x.pdf", pdf_bytes=b"%PDF")


async def test_convert_passes_through_json_string(monkeypatch) -> None:
    # Some docling-serve builds may already serialize json_content as a
    # string; we pass it through unchanged in that case.
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"document": {"json_content": '{"name":"already-string"}'}},
        )

    _patch_client(monkeypatch, handler)

    converter = ServePdfConverter(base_url="http://serve.example")
    out = await converter.convert(filename="x.pdf", pdf_bytes=b"%PDF")
    assert out == '{"name":"already-string"}'
