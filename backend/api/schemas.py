"""Pydantic schemas — wire contract for the debugger UI.

camelCase via `alias_generator`. Domain dataclasses stay snake_case; these
schemas are the conversion boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class HealthResponse(_Base):
    status: str
    version: str
    reasoning_available: bool
    enrich_available: bool = False
    pdf_conversion_available: bool = False


class ReasoningStepSchema(_Base):
    id: str
    kind: str
    title: str
    summary: str
    duration_ms: int
    token_count: int
    citations: list[str]
    payload: dict


class ReasoningTraceSchema(_Base):
    answer: str
    converged: bool
    steps: list[ReasoningStepSchema]
    total_duration_ms: int
    tokens_in: int
    tokens_out: int
    model_id: str


class ReasoningRunRequest(_Base):
    """The client posts a raw DoclingDocument JSON string + the query.

    `document_json` is the serialized `DoclingDocument` (as produced by
    Docling Studio's analysis pipeline, or any docling-core run). It's a
    string so the wire payload stays self-describing and we don't lock the
    UI into a particular intermediate shape.
    """

    document_json: str
    query: str
    model_id: str | None = None


# --- Enrich ----------------------------------------------------------------


class NodeEnrichmentSchema(_Base):
    """One enrichment attached to one node. `value` is intentionally
    untyped on the wire — its shape varies per operation (str for
    summarize, list for keywords/entities, dict for classify)."""

    self_ref: str
    operation: str
    # Pydantic `Any` on the wire. The UI applies a per-operation renderer.
    value: object | None = None


class EnrichTraceSchema(_Base):
    document_json: str
    enrichments: list[NodeEnrichmentSchema]
    operations: list[str]
    total_duration_ms: int
    model_id: str


class EnrichRunRequest(_Base):
    """Operations is a list of `summarize` / `keywords` / `entities` /
    `classify`. Empty list is rejected with a 400. `model_id` overrides
    the backend default for this run only."""

    document_json: str
    operations: list[str]
    model_id: str | None = None
