# docling-lens

Agent debugger for [docling-agent](https://github.com/docling-project/docling-agent).

Standalone companion to **Docling Studio**: upload a PDF (or load a pre-converted
`DoclingDocument` JSON), pick an agent mode, run, watch every step it takes against
the document. Two modes today:

- **RAG** — `DoclingRAGAgent`'s chunkless reasoning loop. A user query produces an
  iteration-by-iteration trace; each step is a section the agent read, with the
  reason it chose it and whether the answer landed.
- **Enrich** — `DoclingEnrichingAgent`'s operations. Pick one or more of
  *summarize / keywords / entities / classify*; the agent walks the document tree
  and attaches metadata. Every enrichment is surfaced both as a typed entry in a
  timeline and as a colored badge on the matching node in the structure tree.

A switch in the top bar toggles between modes; the loaded document and the
focused element are kept in sync across both. PDF pages render with bbox
overlays — click any step, enrichment, or tree node and the matching region
lights up in the PDF.

## Stack

- **Backend** (`backend/`) — FastAPI + Python 3.12 + docling-agent + Mellea
  (Ollama backend) + docling-serve (HTTP, for PDF conversion). Hexagonal
  architecture (ports + adapters). Ruff + pytest.
- **Frontend** (`frontend/`) — Vue 3 (strict TS) + Vite + Pinia + Vitest +
  pdfjs-dist. Feature-based layout with a shared workspace shell.

## Endpoints

| Method | Path | Purpose | Disabled when |
|---|---|---|---|
| POST | `/api/documents` | Upload a PDF → `DoclingDocument` JSON (via docling-serve) | `DOCLING_SERVE_URL` unset |
| POST | `/api/reasoning` | Run `DoclingRAGAgent._rag_loop` | `REASONING_ENABLED=false` or agent deps missing |
| POST | `/api/enrich` | Run `DoclingEnrichingAgent` with explicit operations | same as above |
| GET  | `/api/health` | Lists which sub-systems are available | — |

Disabled endpoints respond 503 with a clear `detail`. Schemas are camelCase
on the wire (`alias_generator=to_camel`) but the Python domain stays
snake_case.

## Repo layout

```
backend/
  domain/        # value objects + ports (zero external deps)
  api/           # FastAPI routers + Pydantic schemas
  infra/         # adapters (Ollama provider, docling-serve, docling-agent runners)
  main.py        # wire-up
  tests/

frontend/
  src/
    shared/
      api/         # http.ts (apiFetch + ApiError), documents.ts, health.ts
      docling/     # parseDoc + useDocTree composable + tests
      stores/      # useDocumentStore (doc + focus), useAppStore (mode)
      workspace/   # WorkspaceShell, TopBar, DocumentPane, PdfViewer, decorations
    features/
      rag/         # conversation + timeline trace + per-step focus
      enrich/      # ops composer + grouped enrichments timeline + tree badges
    App.vue        # routes to RagDebuggerPage or EnrichDebuggerPage by appStore.mode
```

See `backend/CLAUDE.md` and `frontend/CLAUDE.md` for the per-side conventions
(lint, format, type-check, test pipelines).

## Running

### Docker (single image, recommended)

```bash
docker build -t docling-lens:latest .

docker run --rm -p 8001:8001 \
  -e REASONING_ENABLED=true \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e DOCLING_SERVE_URL=http://host.docker.internal:5001 \
  --add-host=host.docker.internal:host-gateway \
  docling-lens:latest
```

Open <http://localhost:8001>. FastAPI serves both the API and the SPA from
the same origin.

**What's in the image**: backend + frontend bundle + the full Python venv
(CPU-only torch). No post-startup downloads. Ollama and docling-serve are
expected to run **outside** the container — point at them via
`OLLAMA_HOST` / `DOCLING_SERVE_URL`.

A `docker-compose.yml` is included as a starter (host-loopback wiring +
healthcheck). Adjust to your setup and `docker compose up`.

Per-feature opt-outs are env vars at boot:
- `FEATURE_RAG=false` — hides the RAG mode from the top-bar toggle
- `FEATURE_ENRICH=false` — hides the Enrich mode

### Local dev (hot reload)

#### Backend

```bash
cd backend
.venv/bin/pip install -r requirements.txt
REASONING_ENABLED=true \
OLLAMA_HOST=http://localhost:11434 \
REASONING_MODEL_ID=mistral-small3.2 \
DOCLING_SERVE_URL=http://localhost:5001 \
CORS_ORIGINS=http://localhost:5173 \
  .venv/bin/uvicorn main:app --reload --port 8001
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173, proxies /api to :8001
```

Open the app, click **Load file** in the right pane, drop a PDF. docling-serve
converts it; the structure tree appears. Use the top-bar toggle to switch
between **rag** and **enrich**. Each mode has its own composer + timeline; the
PDF + structure tree are shared.
