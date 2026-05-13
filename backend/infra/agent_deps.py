"""Shared dep-availability check for docling-agent adapters.

Both the RAG and Enrich adapters import docling-agent + mellea + docling-
core at run-time. The import probe is identical across them, so it lives
here instead of being duplicated in each adapter.
"""

from __future__ import annotations


def deps_present() -> bool:
    """True if docling-agent + mellea are importable. Falls back to
    False on ImportError so the backend boots cleanly when the heavy
    LLM stack isn't installed (e.g. UI-only dev environment)."""
    try:
        import docling_agent.agents  # noqa: F401
        import mellea  # noqa: F401
    except ImportError:
        return False
    return True
