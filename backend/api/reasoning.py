"""Reasoning API — HTTP layer over a `ReasoningRunner` port.

`POST /api/reasoning` invokes the wired-up `ReasoningRunner` against the
DoclingDocument JSON provided by the client and returns a
`ReasoningTraceSchema` shaped for the debugger UI.

Zero coupling to docling-agent / mellea here — the runner (concrete adapter
in `infra/docling_agent_reasoning.py`) is set on `app.state.reasoning_runner`
at boot when `REASONING_ENABLED=true` and the deps are importable. Otherwise
it stays `None` and we 503.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from api.schemas import ReasoningRunRequest, ReasoningStepSchema, ReasoningTraceSchema
from domain.ports import ReasoningParseError, ReasoningRunner
from infra.trace_builder import build_trace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reasoning"])


@router.post("/reasoning", response_model=ReasoningTraceSchema)
async def run_reasoning(body: ReasoningRunRequest, request: Request) -> ReasoningTraceSchema:
    runner: ReasoningRunner | None = getattr(request.app.state, "reasoning_runner", None)
    if runner is None or not runner.is_available:
        raise HTTPException(
            status_code=503,
            detail=(
                "Live reasoning disabled (REASONING_ENABLED=false or docling-agent not installed)"
            ),
        )

    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")
    if not body.document_json.strip():
        raise HTTPException(status_code=400, detail="document_json must not be empty")

    started = time.perf_counter()
    try:
        result = await runner.run(
            document_json=body.document_json,
            query=body.query,
            model_id=body.model_id,
        )
    except ReasoningParseError as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"The model '{e.model_id}' couldn't produce a parseable "
                "answer after retries. Try a different model (e.g. "
                "mistral-small3.2) or rephrase the question."
            ),
        ) from e
    except Exception as e:
        logger.exception("Reasoning loop failed")
        raise HTTPException(status_code=500, detail=f"Reasoning loop failed: {e}") from e

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    trace = build_trace(
        result=result,
        model_id=body.model_id or "",
        total_duration_ms=elapsed_ms,
    )
    return ReasoningTraceSchema(
        answer=trace.answer,
        converged=trace.converged,
        steps=[
            ReasoningStepSchema(
                id=s.id,
                kind=s.kind.value,
                title=s.title,
                summary=s.summary,
                duration_ms=s.duration_ms,
                token_count=s.token_count,
                citations=s.citations,
                payload=s.payload,
            )
            for s in trace.steps
        ],
        total_duration_ms=trace.total_duration_ms,
        tokens_in=trace.tokens_in,
        tokens_out=trace.tokens_out,
        model_id=trace.model_id,
    )
