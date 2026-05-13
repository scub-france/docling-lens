"""Enrich API — HTTP layer over an `EnrichRunner` port.

`POST /api/enrich` runs one or more enrichment operations (summarize /
keywords / entities / classify) over the supplied DoclingDocument JSON
and returns both the enriched JSON and a UI-ready flat projection of
what changed.

Zero coupling to docling-agent here — the runner is wired on
`app.state.enrich_runner` at boot and stays `None` if `REASONING_ENABLED`
is false or the agent deps aren't installed, in which case we 503.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from api.schemas import EnrichRunRequest, EnrichTraceSchema, NodeEnrichmentSchema
from domain.value_objects import EnrichOperation

if TYPE_CHECKING:
    from domain.ports import EnrichRunner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["enrich"])


def _parse_operations(raw: list[str]) -> list[EnrichOperation]:
    """Translate wire strings to the enum, raising 400 on the first
    unknown op rather than silently dropping it — the user spelled
    something the backend doesn't know and deserves to hear about it."""
    valid = {op.value: op for op in EnrichOperation}
    out: list[EnrichOperation] = []
    seen: set[EnrichOperation] = set()
    for name in raw:
        op = valid.get(name)
        if op is None:
            raise HTTPException(
                status_code=400,
                detail=(f"Unknown enrich operation: {name!r}. Expected one of {sorted(valid)}."),
            )
        # De-dupe while preserving order — sending {summarize, summarize}
        # would otherwise force the agent to do the same work twice.
        if op not in seen:
            out.append(op)
            seen.add(op)
    return out


@router.post("/enrich", response_model=EnrichTraceSchema)
async def run_enrich(body: EnrichRunRequest, request: Request) -> EnrichTraceSchema:
    runner: EnrichRunner | None = getattr(request.app.state, "enrich_runner", None)
    if runner is None or not runner.is_available:
        raise HTTPException(
            status_code=503,
            detail=(
                "Live enrich disabled (REASONING_ENABLED=false or docling-agent not installed)"
            ),
        )

    if not body.document_json.strip():
        raise HTTPException(status_code=400, detail="document_json must not be empty")
    if not body.operations:
        raise HTTPException(status_code=400, detail="operations must not be empty")

    operations = _parse_operations(body.operations)

    started = time.perf_counter()
    try:
        result = await runner.run(
            document_json=body.document_json,
            operations=operations,
            model_id=body.model_id,
        )
    except Exception as e:
        logger.exception("Enrich run failed")
        raise HTTPException(status_code=500, detail=f"Enrich run failed: {e}") from e

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return EnrichTraceSchema(
        document_json=result.document_json,
        enrichments=[
            NodeEnrichmentSchema(
                self_ref=e.self_ref,
                operation=e.operation.value,
                value=e.value,
            )
            for e in result.enrichments
        ],
        operations=[op.value for op in result.operations],
        total_duration_ms=elapsed_ms,
        model_id=body.model_id or "",
    )
