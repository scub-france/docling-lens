"""Runtime settings — read once from env, used as a frozen-ish singleton.

Kept dependency-free (no pydantic-settings) to keep the import graph small.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [s.strip() for s in raw.split(",") if s.strip()]


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "0.1.0"))
    cors_origins: list[str] = field(
        default_factory=lambda: _csv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    )

    # Global LLM-stack gate. When false, NO agent runner is wired (no Ollama
    # provider built either) — useful for UI-only dev environments where the
    # heavy docling-agent + mellea deps aren't installed. Off by default so
    # the backend boots without surprises; flip to true in real envs.
    reasoning_enabled: bool = field(default_factory=lambda: _bool("REASONING_ENABLED", False))

    # Per-agent feature flags — layered ON TOP of `reasoning_enabled`. Both
    # default ON so a fresh `REASONING_ENABLED=true` deployment exposes
    # every agent; opt-out by setting the corresponding flag to false.
    # Adding a new agent (extract / write / edit / …): one more entry
    # here + a one-line gate in main.py's wire-up.
    feature_rag: bool = field(default_factory=lambda: _bool("FEATURE_RAG", True))
    feature_enrich: bool = field(default_factory=lambda: _bool("FEATURE_ENRICH", True))

    llm_provider_type: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER_TYPE", "ollama"))
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    reasoning_model_id: str = field(
        default_factory=lambda: os.getenv("REASONING_MODEL_ID", "mistral-small3.2")
    )
    # Hard ceiling on uploaded PDFs. 25 MiB is a generous default for a
    # debugger; bump via env if you're inspecting whole books.
    max_pdf_size_mb: int = field(default_factory=lambda: _int("MAX_PDF_SIZE_MB", 25))

    # Remote docling-serve instance — the ONLY way docling-lens converts
    # PDFs. We deliberately don't bundle the docling library (torch +
    # pypdfium2 + table-structure model). Leaving DOCLING_SERVE_URL unset
    # disables the /api/documents endpoint (503).
    docling_serve_url: str = field(default_factory=lambda: os.getenv("DOCLING_SERVE_URL", ""))
    docling_serve_api_key: str | None = field(
        default_factory=lambda: os.getenv("DOCLING_SERVE_API_KEY") or None
    )
    docling_serve_timeout_s: int = field(
        default_factory=lambda: _int("DOCLING_SERVE_TIMEOUT_S", 600)
    )


settings = Settings()
