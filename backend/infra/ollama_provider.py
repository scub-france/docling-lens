"""Ollama `LLMProvider` adapter.

Carries host + default model id for the reasoning runner. We don't probe
Ollama upfront — unreachable-host errors surface at request time as 5xx
from the API layer, which is enough for a debugger.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects import LLMProviderType


@dataclass(frozen=True)
class OllamaProvider:
    host: str
    default_model_id: str

    @property
    def type(self) -> LLMProviderType:
        return LLMProviderType.OLLAMA
