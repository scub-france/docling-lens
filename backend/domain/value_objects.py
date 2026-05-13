"""Domain value objects — pure data, no external deps.

These mirror the upstream `docling-agent` shapes (`ReasoningIteration` /
`ReasoningResult`) plus a richer step model the debugger UI consumes:
the loop today only emits READ-style iterations, but the trace surface is
prepared for PLAN/RETRIEVE/RERANK/MAP steps that future agents may produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class LLMProviderType(StrEnum):
    """LLM backends the reasoning runner can talk to.

    Today only OLLAMA is realizable: docling-agent v0.1.0 is hardwired to
    Ollama via mellea's `setup_local_session`. Variants are kept so adapters
    can dispatch on the type tag once an upstream provider abstraction lands
    (see https://github.com/docling-project/docling-agent/issues/26).
    """

    OLLAMA = "ollama"


class ReasoningStepKind(StrEnum):
    """Canonical step kinds rendered by the debugger trace pane.

    `READ` covers every iteration produced by docling-agent v0.1.0's
    `_rag_loop`. The other kinds are reserved for richer agent traces:
    a planner emits `PLAN`, a vector retrieval emits `RETRIEVE`, a
    reranker emits `RERANK`, a self-check emits `VERIFY`, and the final
    composition emits `ANSWER`. `MAP` is the structural-overview view.

    The enum is kept in lockstep with the TypeScript `ReasoningStepKind`
    union so the wire contract is symmetric — adding a kind to one side
    without the other is a refactoring trap.
    """

    PLAN = "plan"
    RETRIEVE = "retrieve"
    RERANK = "rerank"
    READ = "read"
    VERIFY = "verify"
    ANSWER = "answer"
    MAP = "map"


@dataclass(frozen=True)
class ReasoningIteration:
    """One step of the docling-agent reasoning loop. Mirrors the upstream
    `RAGIteration` shape exactly so serialization is 1:1."""

    iteration: int
    section_ref: str
    reason: str
    section_text_length: int
    can_answer: bool
    response: str


@dataclass(frozen=True)
class ReasoningStep:
    """Generic trace step the UI renders.

    `payload` is opaque JSON-safe data the trace pane shows under the
    `AGENT.*` block in the inspector. For `READ` steps produced from
    docling-agent iterations, it carries `{cite, extracted, ...}`.
    """

    id: str
    kind: ReasoningStepKind
    title: str
    summary: str
    duration_ms: int = 0
    token_count: int = 0
    citations: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReasoningResult:
    """Raw docling-agent result — kept for serialization parity with traces
    produced outside docling-lens (sidecar JSON, external runs)."""

    answer: str
    iterations: list[ReasoningIteration]
    converged: bool


@dataclass(frozen=True)
class ReasoningTrace:
    """Full debugger payload: the answer plus a rendered step sequence
    derived from the underlying `ReasoningResult`. The frontend consumes
    this shape directly."""

    answer: str
    converged: bool
    steps: list[ReasoningStep]
    total_duration_ms: int
    tokens_in: int
    tokens_out: int
    model_id: str


# --- Enrich (DoclingEnrichingAgent) ----------------------------------------


class EnrichOperation(StrEnum):
    """Operations the enriching agent can apply to a document.

    Names match `docling_agent.agent.enricher._OP_ALIASES` short forms so
    the wire contract feeds the agent directly.

    docling-agent v0.1.0 implements three ops:
      SUMMARIZE → `meta.summary.text` (SummaryMetaField, standard)
      KEYWORDS  → `meta.docling_agent__keywords` (extra field; list[str])
      ENTITIES  → `meta.docling_agent__entities` (extra field; list[dict])

    Each op enriches only items where the agent decides it's meaningful:
    titles, section headers (with subtree text ≥ 100 chars), tables, and
    pictures — NOT paragraphs, list items, or captions.

    `classify_items` is declared in `_OP_ALIASES` upstream but no method
    implements it in v0.1.0 → we don't expose it. Track upstream before
    re-adding.
    """

    SUMMARIZE = "summarize"
    KEYWORDS = "keywords"
    ENTITIES = "entities"


@dataclass(frozen=True)
class NodeEnrichment:
    """One enrichment attached to one node of the document.

    `value` shape varies by operation:
      SUMMARIZE → str
      KEYWORDS  → list[str]
      ENTITIES  → list[str] | list[dict[str, str]]    (model-dependent)
      CLASSIFY  → str  (class label of the highest-confidence prediction)

    Typed as `object` here rather than over-engineered union — the wire
    schema serializes as `Any`. The UI applies a per-operation renderer;
    adding a future operation upstream doesn't force a schema migration.
    """

    self_ref: str
    operation: EnrichOperation
    value: object


@dataclass(frozen=True)
class EnrichResult:
    """Output of one enrich run.

    `document_json` is the fresh DoclingDocument JSON with `meta` fields
    populated. `enrichments` is the UI-ready flat projection — produced
    by walking the enriched doc once in the adapter so the frontend
    doesn't have to re-walk it.
    """

    document_json: str
    enrichments: list[NodeEnrichment]
    operations: list[EnrichOperation]
