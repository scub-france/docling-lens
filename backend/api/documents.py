"""Documents API — single endpoint that ingests a PDF and returns the
serialized `DoclingDocument` JSON the reasoning runner will consume.

We do the conversion server-side (Docling is heavy + native code), then hand
the JSON back to the client. The client owns the document JSON for the
session — there's no server-side persistence. Subsequent reasoning calls
re-submit the JSON in the request body, keeping the backend stateless and
the trace reproducible from the client.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

if TYPE_CHECKING:
    from domain.ports import PdfConverter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


class ConvertResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    filename: str
    document_json: str
    size_bytes: int


def _max_upload_bytes(request: Request) -> int:
    """Per-request lookup of the upload ceiling. The wire-up in `main.py`
    publishes it on `app.state`, so the handler stays free of an `infra`
    import. 0 = no limit."""
    mb = getattr(request.app.state, "max_pdf_size_mb", 0)
    return int(mb) * 1024 * 1024 if mb else 0


@router.post("/documents", response_model=ConvertResponse)
async def convert_pdf(request: Request, file: UploadFile = File(...)) -> ConvertResponse:
    converter: PdfConverter | None = getattr(request.app.state, "pdf_converter", None)
    if converter is None or not converter.is_available:
        raise HTTPException(
            status_code=503,
            detail="PDF conversion disabled (docling not installed)",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    max_bytes = _max_upload_bytes(request)
    if max_bytes > 0 and len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds {max_bytes // (1024 * 1024)} MiB limit",
        )

    try:
        document_json = await converter.convert(filename=file.filename, pdf_bytes=raw)
    except Exception as e:
        logger.exception("PDF conversion failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}") from e

    return ConvertResponse(
        filename=file.filename,
        document_json=document_json,
        size_bytes=len(raw),
    )
