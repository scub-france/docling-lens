"""Domain ports — abstract contracts the API layer depends on.

Adapters live in `infra/`. Keeping ports in `domain/` means the HTTP layer
imports neither docling-agent nor httpx directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from domain.value_objects import (
        EnrichOperation,
        EnrichResult,
        LLMProviderType,
        ReasoningResult,
    )


class ReasoningParseError(Exception):
    """Raised by a `ReasoningRunner` when the upstream LLM couldn't produce
    a parseable answer after retries. The API layer maps this to 502."""

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(f"{model_id}: {reason}")
        self.model_id = model_id
        self.reason = reason


@runtime_checkable
class LLMProvider(Protocol):
    """Connection-level abstraction over an LLM backend.

    Carries the host/base-URL, the default model identifier, and a type tag
    adapters dispatch on. Today only `OllamaProvider` is implemented since
    docling-agent v0.1.0 is hardwired to Ollama via mellea.
    """

    @property
    def type(self) -> LLMProviderType: ...

    @property
    def host(self) -> str: ...

    @property
    def default_model_id(self) -> str: ...


@runtime_checkable
class ReasoningRunner(Protocol):
    """Port for live reasoning over a previously-converted document.

    Takes the serialized `DoclingDocument` JSON + a user query + optional
    per-call model override, returns a `ReasoningResult`.

    Adapters MUST translate upstream parsing failures into
    `ReasoningParseError`. Other exceptions propagate as-is.
    """

    @property
    def is_available(self) -> bool:
        """True if the runner can serve requests (deps importable +
        provider wired). Used to short-circuit to 503."""
        ...

    async def run(
        self,
        *,
        document_json: str,
        query: str,
        model_id: str | None = None,
    ) -> ReasoningResult:
        """Execute the reasoning loop. `model_id` overrides the provider's
        default for this call only."""
        ...


@runtime_checkable
class EnrichRunner(Protocol):
    """Port for `DoclingEnrichingAgent`.

    Applies one or more enrichment operations (summarize / keywords /
    entities / classify) to a DoclingDocument and returns both the
    enriched JSON and a flat UI-ready projection of what changed.

    Adapters MUST accept an explicit `operations` list (we bypass the
    agent's LLM router upstream — see enricher.py:104-113). Empty list
    is a 400 at the API layer, not a passthrough.
    """

    @property
    def is_available(self) -> bool: ...

    async def run(
        self,
        *,
        document_json: str,
        operations: list[EnrichOperation],
        model_id: str | None = None,
    ) -> EnrichResult: ...


@runtime_checkable
class PdfConverter(Protocol):
    """Port for turning a raw PDF (bytes) into a serialized
    `DoclingDocument` JSON the reasoning runner consumes.

    The adapter is thread-locked and offloaded to a worker thread (Docling's
    converter is sync + not thread-safe), so the API layer can `await` it
    without blocking the event loop.
    """

    @property
    def is_available(self) -> bool: ...

    async def convert(self, *, filename: str, pdf_bytes: bytes) -> str:
        """Return the serialized DoclingDocument JSON."""
        ...
