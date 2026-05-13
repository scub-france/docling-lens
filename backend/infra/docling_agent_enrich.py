"""docling-agent enrich runner adapter.

Implements `EnrichRunner` over `DoclingEnrichingAgent`. Crucially, we
pass `operations=[...]` explicitly to `agent.run` — that path bypasses
the agent's LLM-based router (see enricher.py:104-113) so the caller
controls exactly which enrichments fire, and the run is deterministic.

What the agent actually does (verified against v0.1.0 source):

  1. PER OP, calls `_fix_heading_levels` first — that instantiates a
     `DoclingEditingAgent` and asks it to correct section levels via
     LLM. So every op costs an EXTRA LLM round-trip before the
     enrichment itself.
  2. Then calls `make_hierarchical_document(doc)` — rebuilds the doc
     tree from scratch via `add_text/add_heading/add_table/add_picture`.
     This generates NEW `self_ref` values AND DROPS `prov` (bbox + page
     info) — the upstream `add_*` helpers don't accept prov.
  3. Walks the new tree, calls the LLM per enriched item, writes to
     `meta`:
        SUMMARIZE → item.meta.summary.text            (SummaryMetaField)
        KEYWORDS  → item.meta.docling_agent__keywords (extra; list[str])
        ENTITIES  → item.meta.docling_agent__entities (extra;
                    list[{entity_type, mention}])
     Only `TitleItem`, `SectionHeaderItem` (subtree text ≥ 100 chars),
     `TableItem`, and `PictureItem` get enriched. Paragraphs, captions,
     list items never do.

Because step 2 drops `prov`, we re-inject it ourselves before returning
the doc (`_reinject_prov` below) so the frontend's PDF bbox overlay still
works against the enriched JSON.

`classify_items` is in `_OP_ALIASES` upstream but no method implements
it in v0.1.0 — calling it would AttributeError. We removed `CLASSIFY`
from `EnrichOperation` until upstream catches up.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

from domain.value_objects import (
    EnrichOperation,
    EnrichResult,
    LLMProviderType,
    NodeEnrichment,
)
from infra.agent_deps import deps_present

if TYPE_CHECKING:
    from domain.ports import LLMProvider

logger = logging.getLogger(__name__)


class DoclingAgentEnrichRunner:
    """EnrichRunner adapter wrapping `DoclingEnrichingAgent`.

    Same SINGLE-INSTANCE-PER-PROCESS invariant as the reasoning runner:
    construction commits the provider's host to `OLLAMA_HOST`. The
    wire-up in `main.py` must share the same `OllamaProvider` between
    the two runners — building two providers with different hosts would
    silently overwrite the env var.
    """

    def __init__(self, provider: LLMProvider) -> None:
        if provider.type is not LLMProviderType.OLLAMA:
            raise NotImplementedError(
                f"docling-agent v0.1.0 only supports Ollama, got provider type {provider.type!r}."
            )
        self._provider = provider
        self._deps_ok = deps_present()
        # Process-wide side effect — see class docstring for the invariant.
        os.environ["OLLAMA_HOST"] = provider.host

    @property
    def is_available(self) -> bool:
        return self._deps_ok

    async def run(
        self,
        *,
        document_json: str,
        operations: list[EnrichOperation],
        model_id: str | None = None,
    ) -> EnrichResult:
        if not self._deps_ok:
            raise RuntimeError("docling-agent / mellea not importable — cannot run enrich")
        if not operations:
            # Defensive — the API layer already rejects empty op lists with 400.
            raise ValueError("operations must not be empty")

        from docling_agent.agents import DoclingEnrichingAgent
        from docling_core.types.doc.document import DoclingDocument
        from mellea.backends.model_ids import ModelIdentifier

        raw_model_id = model_id or self._provider.default_model_id
        wrapped_model_id = ModelIdentifier(ollama_name=raw_model_id)

        try:
            doc = DoclingDocument.model_validate_json(document_json)
        except Exception as e:
            raise RuntimeError(f"Failed to parse document_json: {e}") from e

        agent = DoclingEnrichingAgent(model_id=wrapped_model_id, tools=[])
        op_values = [op.value for op in operations]
        logger.info(
            "Enrich run: model_id=%s ollama_host=%s ops=%s",
            raw_model_id,
            self._provider.host,
            op_values,
        )

        # The agent is sync + LLM-heavy (N items * M ops * Ollama latency,
        # plus an extra LLM pass per op for `_fix_heading_levels`).
        # Offload to a worker thread so the event loop stays responsive;
        # cancellation of the FastAPI request will NOT stop the worker —
        # see the cancellation note in the README.
        enriched: DoclingDocument = await asyncio.to_thread(
            agent.run,
            task="",  # ignored when `operations` is supplied (enricher.py:104)
            document=doc,
            operations=op_values,
        )

        # docling-agent's `make_hierarchical_document` rebuilds the doc via
        # `add_text/add_heading/add_table/add_picture`, which drop `prov`.
        # The frontend's PDF bbox overlay needs prov, so we re-inject it
        # from the original `doc` before returning.
        _reinject_prov(source_doc=doc, enriched_doc=enriched)

        enrichments = _collect_enrichments(enriched, operations)
        return EnrichResult(
            document_json=enriched.model_dump_json(),
            enrichments=enrichments,
            operations=operations,
        )


def _collect_enrichments(doc: Any, requested_ops: list[EnrichOperation]) -> list[NodeEnrichment]:
    """Walk every text/table/picture/group item, read its `meta`, and
    emit a `NodeEnrichment` for each requested operation that actually
    populated a field. Items the agent skipped (e.g. classify on a text
    item) simply produce no entry — that's expected.
    """
    out: list[NodeEnrichment] = []
    requested = set(requested_ops)
    for self_ref, item in _iter_doc_items(doc):
        meta = getattr(item, "meta", None)
        if meta is None:
            continue
        for op in requested:
            value = _extract_meta_value(meta, op)
            if value is None:
                continue
            out.append(NodeEnrichment(self_ref=self_ref, operation=op, value=value))
    return out


def _iter_doc_items(doc: Any):
    """Yield `(self_ref, item)` for every node in a DoclingDocument that
    can carry meta. Order is: texts → tables → pictures → groups, matching
    upstream attribute order. Items missing `self_ref` are skipped (rare
    defensive case — every item gets one from docling-core)."""
    for attr in ("texts", "tables", "pictures", "groups"):
        coll = getattr(doc, attr, None)
        if not coll:
            continue
        for item in coll:
            self_ref = getattr(item, "self_ref", None)
            if isinstance(self_ref, str):
                yield self_ref, item


def _extract_meta_value(meta: Any, op: EnrichOperation) -> object | None:
    """Read the op-specific value out of `meta`, returning None when the
    operation didn't apply to this node. Reads are defensive so a meta
    object missing the optional attribute doesn't blow up the walk."""
    if op is EnrichOperation.SUMMARIZE:
        summary = getattr(meta, "summary", None)
        if summary is None:
            return None
        # `SummaryMetaField` is a Pydantic model with `.text`. Fall back to
        # raw value if upstream ever returns a plain str.
        return getattr(summary, "text", summary)

    if op is EnrichOperation.KEYWORDS:
        # Extra field — `_ExtraAllowingModel` exposes them as plain attributes.
        return getattr(meta, "docling_agent__keywords", None)

    if op is EnrichOperation.ENTITIES:
        # list[{entity_type: str, mention: str}] per docling-agent's
        # `_generate_entities` validation contract.
        return getattr(meta, "docling_agent__entities", None)

    return None


def _reinject_prov(*, source_doc: Any, enriched_doc: Any) -> None:
    """Restore `prov` on the enriched doc by mapping items back to the
    source doc.

    docling-agent's `make_hierarchical_document` recreates every item
    via `add_text/add_heading/add_table/add_picture`, none of which
    accept a `prov` argument. The enriched doc therefore comes back
    structurally enriched but spatially blind — `prov[0].page_no` and
    `prov[0].bbox` are gone, so the frontend's PDF overlay has nothing
    to draw.

    Strategy:
      - `texts` (paragraphs, section headers, titles, captions) and
        `groups`: match by `(label, text)` in document order via FIFO
        queues. Duplicates (e.g. multiple `text = "1"`) resolve in the
        order the agent emitted them, which mirrors the source order.
      - `tables` / `pictures`: align positionally (i-th source = i-th
        enriched). `_copy_table` / `_copy_picture` walk the source in
        document order, so indices stay aligned even when the body tree
        gets restructured.

    Items the source doesn't carry prov for (rare; e.g. captions newly
    synthesized by the agent) are left untouched.

    Mutates `enriched_doc` in place — no return value.
    """
    from collections import defaultdict
    from collections.abc import Iterable

    def _key(item: Any) -> tuple[str, str]:
        return (str(getattr(item, "label", "") or ""), str(getattr(item, "text", "") or ""))

    def _has_real_prov(item: Any) -> bool:
        prov = getattr(item, "prov", None)
        return bool(prov)

    # Text-like items: queue by (label, text). docling-core stores every
    # text-bearing item in `.texts`, so one walk covers paragraphs +
    # section_headers + titles + captions.
    text_queue: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for item in getattr(source_doc, "texts", None) or []:
        if _has_real_prov(item):
            text_queue[_key(item)].append(item.prov)

    matched = 0
    missed = 0
    for item in getattr(enriched_doc, "texts", None) or []:
        queue = text_queue.get(_key(item))
        if queue:
            item.prov = queue.pop(0)
            matched += 1
        else:
            missed += 1

    def _zip_prov(src: Iterable[Any], dst: Iterable[Any]) -> tuple[int, int]:
        m = 0
        n = 0
        for s, d in zip(src, dst, strict=False):
            if _has_real_prov(s):
                d.prov = s.prov
                m += 1
            else:
                n += 1
        return m, n

    t_m, t_n = _zip_prov(
        getattr(source_doc, "tables", None) or [],
        getattr(enriched_doc, "tables", None) or [],
    )
    p_m, p_n = _zip_prov(
        getattr(source_doc, "pictures", None) or [],
        getattr(enriched_doc, "pictures", None) or [],
    )

    logger.info(
        "Re-injected prov: texts %d matched / %d missed; "
        "tables %d matched / %d missed; pictures %d matched / %d missed",
        matched,
        missed,
        t_m,
        t_n,
        p_m,
        p_n,
    )
