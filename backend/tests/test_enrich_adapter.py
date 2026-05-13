"""Tests for `_collect_enrichments` — the pure walker that turns an
enriched DoclingDocument into a flat list of NodeEnrichments. We mock
the docling-core item shape with simple namespace objects rather than
pulling in the real schema, so the test runs without the LLM stack.
"""

from __future__ import annotations

from types import SimpleNamespace

from domain.value_objects import EnrichOperation
from infra.docling_agent_enrich import _collect_enrichments


def _doc(**collections) -> SimpleNamespace:
    """Build a minimal duck-typed DoclingDocument for the walker.
    Missing attributes fall back to empty so we only declare what
    each test cares about."""
    return SimpleNamespace(
        texts=collections.get("texts", []),
        tables=collections.get("tables", []),
        pictures=collections.get("pictures", []),
        groups=collections.get("groups", []),
    )


def _meta(**fields) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def test_summarize_reads_meta_summary_text() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/0",
                meta=_meta(summary=SimpleNamespace(text="Intro paragraph summary.")),
            ),
        ]
    )
    out = _collect_enrichments(doc, [EnrichOperation.SUMMARIZE])
    assert len(out) == 1
    assert out[0].self_ref == "#/texts/0"
    assert out[0].operation is EnrichOperation.SUMMARIZE
    assert out[0].value == "Intro paragraph summary."


def test_keywords_and_entities_read_extra_fields() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/1",
                meta=_meta(
                    docling_agent__keywords=["docling", "pdf"],
                    docling_agent__entities=["IBM", "Granite"],
                ),
            ),
        ]
    )
    out = _collect_enrichments(doc, [EnrichOperation.KEYWORDS, EnrichOperation.ENTITIES])
    assert {e.operation for e in out} == {
        EnrichOperation.KEYWORDS,
        EnrichOperation.ENTITIES,
    }
    by_op = {e.operation: e.value for e in out}
    assert by_op[EnrichOperation.KEYWORDS] == ["docling", "pdf"]
    assert by_op[EnrichOperation.ENTITIES] == ["IBM", "Granite"]


def test_entities_returns_raw_list_of_mention_dicts() -> None:
    # docling-agent's `_generate_entities` returns list[{entity_type, mention}];
    # the adapter passes it through unchanged — the frontend renders.
    entities = [
        {"entity_type": "PERSON", "mention": "Christoph Auer"},
        {"entity_type": "ORG", "mention": "IBM"},
    ]
    doc = _doc(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/0",
                meta=_meta(docling_agent__entities=entities),
            ),
        ]
    )
    out = _collect_enrichments(doc, [EnrichOperation.ENTITIES])
    assert len(out) == 1
    assert out[0].value == entities


def test_missing_meta_field_produces_no_entry() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(self_ref="#/texts/0", meta=_meta()),  # nothing set
        ]
    )
    out = _collect_enrichments(
        doc,
        [
            EnrichOperation.SUMMARIZE,
            EnrichOperation.KEYWORDS,
            EnrichOperation.ENTITIES,
        ],
    )
    assert out == []


def test_only_requested_operations_are_collected() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/0",
                meta=_meta(
                    summary=SimpleNamespace(text="…"),
                    docling_agent__keywords=["x"],
                ),
            )
        ]
    )
    # Even though the doc has both, only summarize was asked for.
    out = _collect_enrichments(doc, [EnrichOperation.SUMMARIZE])
    assert {e.operation for e in out} == {EnrichOperation.SUMMARIZE}


def test_items_without_meta_are_skipped() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(self_ref="#/texts/0", meta=None),
            SimpleNamespace(
                self_ref="#/texts/1",
                meta=_meta(summary=SimpleNamespace(text="kept")),
            ),
        ]
    )
    out = _collect_enrichments(doc, [EnrichOperation.SUMMARIZE])
    assert [e.self_ref for e in out] == ["#/texts/1"]


def test_walk_order_is_texts_then_tables_then_pictures_then_groups() -> None:
    doc = _doc(
        texts=[
            SimpleNamespace(
                self_ref="#/texts/0",
                meta=_meta(summary=SimpleNamespace(text="t")),
            )
        ],
        tables=[
            SimpleNamespace(
                self_ref="#/tables/0",
                meta=_meta(summary=SimpleNamespace(text="tb")),
            )
        ],
        pictures=[
            SimpleNamespace(
                self_ref="#/pictures/0",
                meta=_meta(summary=SimpleNamespace(text="p")),
            )
        ],
        groups=[
            SimpleNamespace(
                self_ref="#/groups/0",
                meta=_meta(summary=SimpleNamespace(text="g")),
            )
        ],
    )
    out = _collect_enrichments(doc, [EnrichOperation.SUMMARIZE])
    assert [e.self_ref for e in out] == [
        "#/texts/0",
        "#/tables/0",
        "#/pictures/0",
        "#/groups/0",
    ]
