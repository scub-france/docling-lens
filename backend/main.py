"""docling-lens backend — FastAPI app.

Endpoints:
- `POST /api/documents` — PDF → DoclingDocument JSON (via docling-serve)
- `POST /api/reasoning` — RAG run via `DoclingRAGAgent`
- `POST /api/enrich` — enrich run via `DoclingEnrichingAgent`
- `GET  /api/health` — surfaces which sub-systems are wired & available

The two agent runners share the same `OllamaProvider` instance — both
mutate `OLLAMA_HOST` in their constructors (process-wide), so they MUST
agree on the host. We build one provider, hand it to both runners, and
never construct a second one.

Everything is wired at boot in the module body. When a dependency is
absent (e.g. `REASONING_ENABLED=false`, docling-agent not installed,
`DOCLING_SERVE_URL` empty), the corresponding `app.state.*` stays `None`
and the matching endpoint responds 503 — the rest of the API boots
cleanly, which keeps UI-only / demo deployments trivial.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.documents import router as documents_router
from api.enrich import router as enrich_router
from api.reasoning import router as reasoning_router
from api.schemas import HealthResponse
from infra.agent_deps import deps_present as _agent_deps_present
from infra.docling_agent_enrich import DoclingAgentEnrichRunner
from infra.docling_agent_reasoning import DoclingAgentReasoningRunner
from infra.ollama_provider import OllamaProvider
from infra.serve_pdf_converter import ServePdfConverter
from infra.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _build_ollama_provider() -> OllamaProvider | None:
    """Single provider shared between the reasoning and enrich runners —
    both mutate `OLLAMA_HOST` at construction, so they MUST see the same
    host. Returns None when the LLM stack isn't configured/installed."""
    if not settings.reasoning_enabled:
        logger.info("Agents disabled (REASONING_ENABLED=false)")
        return None
    if not _agent_deps_present():
        logger.warning(
            "REASONING_ENABLED=true but docling-agent / mellea not importable "
            "— agent runners disabled"
        )
        return None
    if settings.llm_provider_type != "ollama":
        logger.warning(
            "Unsupported LLM_PROVIDER_TYPE=%s — only 'ollama' is realizable today",
            settings.llm_provider_type,
        )
        return None
    return OllamaProvider(
        host=settings.ollama_host,
        default_model_id=settings.reasoning_model_id,
    )


app = FastAPI(
    title="docling-lens",
    description="Agent debugger for Docling reasoning traces",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def _build_pdf_converter() -> ServePdfConverter | None:
    if not settings.docling_serve_url:
        logger.info("DOCLING_SERVE_URL not set — PDF upload endpoint disabled")
        return None
    logger.info("Using docling-serve at %s", settings.docling_serve_url)
    return ServePdfConverter(
        base_url=settings.docling_serve_url,
        api_key=settings.docling_serve_api_key,
        timeout_s=settings.docling_serve_timeout_s,
    )


_provider = _build_ollama_provider()
app.state.reasoning_runner = (
    DoclingAgentReasoningRunner(provider=_provider) if _provider is not None else None
)
app.state.enrich_runner = (
    DoclingAgentEnrichRunner(provider=_provider) if _provider is not None else None
)
app.state.pdf_converter = _build_pdf_converter()
# Publish per-request config on app.state so handlers don't import infra.settings.
app.state.max_pdf_size_mb = settings.max_pdf_size_mb

app.include_router(reasoning_router)
app.include_router(enrich_router)
app.include_router(documents_router)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    reasoning_runner = getattr(app.state, "reasoning_runner", None)
    enrich_runner = getattr(app.state, "enrich_runner", None)
    converter = getattr(app.state, "pdf_converter", None)
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        reasoning_available=reasoning_runner is not None and reasoning_runner.is_available,
        enrich_available=enrich_runner is not None and enrich_runner.is_available,
        pdf_conversion_available=converter is not None and converter.is_available,
    )
