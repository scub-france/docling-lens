"""Tests for `_reinject_prov` — the helper that copies `prov` from the
source doc onto the enriched doc, since docling-agent's
`make_hierarchical_document` recreates items via `add_*` and drops prov
in the process.

We duck-type DoclingDocument with SimpleNamespace so the tests run
without the LLM stack and without docling-core's pydantic validation.
"""

from __future__ import annotations

from types import SimpleNamespace

from infra.docling_agent_enrich import _reinject_prov


def _text(self_ref: str, label: str, text: str, prov=None) -> SimpleNamespace:
    return SimpleNamespace(self_ref=self_ref, label=label, text=text, prov=prov or [])


def _table(self_ref: str, prov=None) -> SimpleNamespace:
    return SimpleNamespace(self_ref=self_ref, prov=prov or [])


def _picture(self_ref: str, prov=None) -> SimpleNamespace:
    return SimpleNamespace(self_ref=self_ref, prov=prov or [])


def _doc(**collections) -> SimpleNamespace:
    return SimpleNamespace(
        texts=collections.get("texts", []),
        tables=collections.get("tables", []),
        pictures=collections.get("pictures", []),
        groups=collections.get("groups", []),
    )


def test_text_match_by_label_and_content_copies_prov() -> None:
    src = _doc(
        texts=[
            _text("#/texts/0", "title", "Docling Technical Report", prov=[{"page_no": 1}]),
            _text("#/texts/1", "section_header", "1 Introduction", prov=[{"page_no": 1}]),
            _text("#/texts/2", "paragraph", "Hello", prov=[{"page_no": 1, "bbox": [0, 0, 10, 10]}]),
        ]
    )
    enr = _doc(
        texts=[
            # Same items, different order (hierarchical) and no prov yet.
            _text("#/texts/0", "title", "Docling Technical Report"),
            _text("#/texts/1", "section_header", "1 Introduction"),
            _text("#/texts/2", "paragraph", "Hello"),
        ]
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.texts[0].prov == [{"page_no": 1}]
    assert enr.texts[1].prov == [{"page_no": 1}]
    assert enr.texts[2].prov == [{"page_no": 1, "bbox": [0, 0, 10, 10]}]


def test_text_duplicates_resolve_via_fifo_in_source_order() -> None:
    # Two items have identical (label, text) — the FIFO queue assigns
    # the first source prov to the first enriched item with the same key.
    src = _doc(
        texts=[
            _text("#/texts/0", "paragraph", "1", prov=[{"page_no": 1}]),
            _text("#/texts/1", "paragraph", "1", prov=[{"page_no": 2}]),
        ]
    )
    enr = _doc(
        texts=[
            _text("#/texts/0", "paragraph", "1"),
            _text("#/texts/1", "paragraph", "1"),
        ]
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.texts[0].prov == [{"page_no": 1}]
    assert enr.texts[1].prov == [{"page_no": 2}]


def test_enriched_text_with_no_match_keeps_prov_empty() -> None:
    src = _doc(texts=[_text("#/texts/0", "paragraph", "Hello", prov=[{"page_no": 1}])])
    enr = _doc(
        texts=[
            _text("#/texts/0", "paragraph", "Hello"),
            _text("#/texts/1", "caption", "Figure 1: …"),  # synthesized, no source match
        ]
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.texts[0].prov == [{"page_no": 1}]
    assert enr.texts[1].prov == []


def test_tables_align_positionally() -> None:
    src = _doc(
        tables=[
            _table("#/tables/0", prov=[{"page_no": 7}]),
            _table("#/tables/1", prov=[{"page_no": 8}]),
        ]
    )
    enr = _doc(
        tables=[
            _table("#/tables/0"),
            _table("#/tables/1"),
        ]
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.tables[0].prov == [{"page_no": 7}]
    assert enr.tables[1].prov == [{"page_no": 8}]


def test_pictures_align_positionally() -> None:
    src = _doc(
        pictures=[
            _picture("#/pictures/0", prov=[{"page_no": 3, "bbox": [0, 0, 100, 100]}]),
        ]
    )
    enr = _doc(pictures=[_picture("#/pictures/0")])

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.pictures[0].prov == [{"page_no": 3, "bbox": [0, 0, 100, 100]}]


def test_extra_enriched_tables_pictures_are_left_untouched() -> None:
    # zip(strict=False) — if enriched has more tables than source for some
    # reason (rare), the extras keep their (empty) prov rather than crash.
    src = _doc(tables=[_table("#/tables/0", prov=[{"page_no": 1}])])
    enr = _doc(
        tables=[
            _table("#/tables/0"),
            _table("#/tables/1"),  # no source counterpart
        ]
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.tables[0].prov == [{"page_no": 1}]
    assert enr.tables[1].prov == []


def test_source_items_without_prov_do_not_overwrite_existing_prov() -> None:
    # Edge case: source item has empty prov, enriched has a prov already
    # (synthesized by the agent somehow). Don't clobber with an empty list.
    src = _doc(texts=[_text("#/texts/0", "paragraph", "Hello")])  # prov=[]
    enr = _doc(
        texts=[_text("#/texts/0", "paragraph", "Hello", prov=[{"page_no": 99}])],
    )

    _reinject_prov(source_doc=src, enriched_doc=enr)

    assert enr.texts[0].prov == [{"page_no": 99}]
