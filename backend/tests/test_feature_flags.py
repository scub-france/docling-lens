"""Tests for the per-agent feature-flag wire-up in `main.py`.

The factories `_build_reasoning_runner` / `_build_enrich_runner` accept
`feature_on` explicitly so we can exercise the flag axis without having
to mutate the frozen `settings` singleton or relaunch the process. The
real settings → flag → factory chain stays a one-liner in main module
scope and is covered indirectly by the rest of the test suite.
"""

from __future__ import annotations

from main import _build_enrich_runner, _build_reasoning_runner


class _FakeProvider:
    """Stand-in for OllamaProvider — the runner constructors only touch
    `provider.type`, `provider.host`, and `provider.default_model_id`,
    and they mutate `os.environ` (single-host invariant). For the flag
    tests we only care about presence, so `None` vs sentinel is enough."""


_SENTINEL = _FakeProvider()


def test_reasoning_runner_none_when_provider_none() -> None:
    # No LLM stack wired → no agent regardless of flag.
    assert _build_reasoning_runner(None, feature_on=True) is None
    assert _build_reasoning_runner(None, feature_on=False) is None


def test_reasoning_runner_none_when_feature_off() -> None:
    # Provider present but the per-agent flag opts out → no runner.
    assert _build_reasoning_runner(_SENTINEL, feature_on=False) is None  # type: ignore[arg-type]


def test_enrich_runner_none_when_provider_none() -> None:
    assert _build_enrich_runner(None, feature_on=True) is None
    assert _build_enrich_runner(None, feature_on=False) is None


def test_enrich_runner_none_when_feature_off() -> None:
    assert _build_enrich_runner(_SENTINEL, feature_on=False) is None  # type: ignore[arg-type]


def test_flags_are_independent() -> None:
    # Disabling RAG must not affect Enrich and vice versa. We only assert
    # that the OFF side returns None; the ON side requires a real
    # OllamaProvider (which would mutate os.environ) so we keep it out
    # of the flag-axis tests — the construction path is covered by
    # `test_enrich_api` / `test_reasoning_api`.
    assert _build_reasoning_runner(_SENTINEL, feature_on=False) is None  # type: ignore[arg-type]
    assert _build_enrich_runner(_SENTINEL, feature_on=False) is None  # type: ignore[arg-type]
