"""Remote PDF → DoclingDocument converter — delegates to docling-serve.

docling-lens stays small on purpose: we do NOT bundle the docling library
(torch + pypdfium2 + table-structure model ~1 GB). Instead we call a
docling-serve instance over HTTP and forward the resulting DoclingDocument
JSON to the agent.

API contract (docling-serve v1):
- POST /v1/convert/file (multipart) — `files` field with the PDF.
- Response: `{"document": {"json_content": <DoclingDocument as dict>, ...}}`
- Auth: `X-Api-Key` header when an API key is configured.
"""

from __future__ import annotations

import json
import logging
import mimetypes

import httpx

logger = logging.getLogger(__name__)

_API_PREFIX = "/v1"


class ServePdfConverter:
    """PdfConverter adapter that talks to a remote docling-serve.

    Stateless apart from base URL + API key — a single instance is shared
    across requests. httpx clients are created per-call to keep timeouts
    request-scoped (a long conversion shouldn't strand a long-lived client).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 600.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_s

    @property
    def is_available(self) -> bool:
        # We don't pre-flight on construction (would block boot); each request
        # surfaces unreachable-server errors as 5xx from the API layer.
        return bool(self._base_url)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-Api-Key"] = self._api_key
        return headers

    async def convert(self, *, filename: str, pdf_bytes: bytes) -> str:
        content_type = mimetypes.guess_type(filename)[0] or "application/pdf"
        # We only ask docling-serve for the JSON representation — the agent
        # walks the DoclingDocument structure directly. md/html are wasted
        # bytes on the wire for this use case.
        form_data: dict[str, str | list[str]] = {
            "to_formats": ["json"],
            "do_ocr": "true",
            "do_table_structure": "true",
            "table_mode": "accurate",
        }
        url = f"{self._base_url}{_API_PREFIX}/convert/file"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                files={"files": (filename, pdf_bytes, content_type)},
                data=form_data,
                headers=self._headers(),
            )

        if response.status_code >= 400:
            logger.error("docling-serve error %d: %s", response.status_code, response.text[:500])
            response.raise_for_status()

        data = response.json()
        document = data.get("document") or {}
        json_content = document.get("json_content")
        if json_content is None:
            raise RuntimeError(
                "docling-serve response missing `document.json_content` — "
                "check the `to_formats` field is honored upstream"
            )
        # The runner calls `DoclingDocument.model_validate_json` which expects
        # a string. Serialize once here so callers can stay JSON-string-typed.
        if isinstance(json_content, str):
            return json_content
        return json.dumps(json_content)
