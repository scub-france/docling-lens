"""Build a `ReasoningTrace` (debugger-facing) from a raw `ReasoningResult`
(docling-agent native).

The trace pane in the UI renders typed steps (PLAN/RETRIEVE/RERANK/READ/MAP).
docling-agent v0.1.0 only emits READ-style iterations, so every iteration
maps 1:1 to a `READ` step. The summary line shows the section the agent
read and whether it answered.

Token / duration values from the upstream loop aren't currently exposed,
so we leave them at zero — they'll get populated once the wider trace API
lands.
"""

from __future__ import annotations

from domain.value_objects import (
    ReasoningIteration,
    ReasoningResult,
    ReasoningStep,
    ReasoningStepKind,
    ReasoningTrace,
)


def _read_step(it: ReasoningIteration) -> ReasoningStep:
    # docling-agent's `reason` is the LLM's stated motivation for picking
    # this section — it's the most informative thing we have per step, so
    # use it as the title. Fall back to the section ref when missing.
    title = it.reason.strip() if it.reason else f"Read {it.section_ref}"
    # Trim long titles so the timeline row doesn't blow up.
    if len(title) > 96:
        title = title[:93].rstrip() + "…"

    if it.can_answer:
        summary = it.response.strip()
    else:
        summary = (
            f"Insufficient — {it.section_text_length} chars read, agent moved on."
            if it.section_text_length
            else "Insufficient — agent moved on."
        )

    return ReasoningStep(
        id=f"s{it.iteration}",
        kind=ReasoningStepKind.READ,
        title=title,
        summary=summary,
        citations=[it.section_ref] if it.section_ref else [],
        payload={
            "iteration": it.iteration,
            "section_ref": it.section_ref,
            "reason": it.reason,
            "section_text_length": it.section_text_length,
            "can_answer": it.can_answer,
            "response": it.response,
        },
    )


def build_trace(
    *,
    result: ReasoningResult,
    model_id: str,
    total_duration_ms: int = 0,
) -> ReasoningTrace:
    """Project a docling-agent `ReasoningResult` onto the debugger-facing
    trace shape. `total_duration_ms` is wall-clock measured by the API
    layer — passed in so the route doesn't have to mutate the returned
    trace afterwards (single source of truth)."""
    steps = [_read_step(it) for it in result.iterations]
    return ReasoningTrace(
        answer=result.answer,
        converged=result.converged,
        steps=steps,
        total_duration_ms=total_duration_ms,
        tokens_in=0,
        tokens_out=0,
        model_id=model_id,
    )
