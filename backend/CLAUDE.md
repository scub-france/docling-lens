# Backend — docling-lens

FastAPI + Python 3.12+ + docling-agent + Ollama + docling-serve (HTTP) + pytest.

**Dépendance volontairement absente :** la lib `docling` n'est PAS installée
ici. La conversion PDF passe par un docling-serve distant (HTTP). docling-lens
reste léger ; le travail lourd est délégué.

## Commandes

```bash
ruff check .              # Lint
ruff check . --fix        # Lint + auto-fix
ruff format .             # Format
pytest tests/ -v          # Tests (asyncio_mode=auto)
uvicorn main:app --reload --port 8001  # Dev server (port 8001 — Studio runs on 8000)
```

## Architecture (Hexagonal — Ports & Adapters)

- `domain/` — Modèles métier purs (dataclasses, StrEnum, Protocol ports).
  Aucune dépendance externe (pas de FastAPI, pas de docling-agent).
- `api/` — Couche HTTP : routers FastAPI, schemas Pydantic. camelCase via
  `alias_generator`. Un router par capacité agent (`reasoning.py`,
  `enrich.py`, `documents.py`).
- `infra/` — Adaptateurs concrets :
  - `docling_agent_reasoning.py` — `DoclingAgentReasoningRunner`
  - `docling_agent_enrich.py` — `DoclingAgentEnrichRunner`
  - `agent_deps.py` — `deps_present()` partagé entre les deux runners
  - `ollama_provider.py` — `OllamaProvider` (un seul, partagé par tous les
    runners — invariant single-host, voir docstring de classe)
  - `serve_pdf_converter.py` — adapter HTTP docling-serve
  - `settings.py` — lecture env, source unique de vérité
  - `trace_builder.py` — projection `ReasoningResult` → `ReasoningTrace`

Pas de couche `persistence/` ni `services/` : docling-lens est un debugger
sans état serveur. Les traces ne sont pas stockées côté serveur.

**Ajouter un nouvel agent docling** (extract, write, edit) suit le même
pattern : value objects + port dans `domain/`, adapter dans
`infra/docling_agent_<name>.py` réutilisant `agent_deps.deps_present()` et
le `OllamaProvider` partagé, router dans `api/<name>.py`, wire-up dans
`main.py` qui partage le provider, tests symétriques à ceux d'enrich.

## Validation pipeline

**Exécuter systématiquement avant de considérer une tâche terminée :**

```bash
.venv/bin/ruff check . --fix
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/ -v
```

Tout nouveau code doit avoir des tests. Zéro violation tolérée.

## Conventions

- **Ruff** : E, W, F, I, N, UP, B, SIM, TCH, RUF. Line-length 100.
- **Imports** : isort first-party = `api`, `domain`, `infra`.
- **Naming** : snake_case en Python. camelCase uniquement dans les schemas
  Pydantic (contrat API).
- **Tests** : pytest-asyncio avec `asyncio_mode = auto`.
- **Env** : voir `.env.example`. Principales : `REASONING_ENABLED` (gate les
  deux agents RAG + Enrich), `OLLAMA_HOST`, `REASONING_MODEL_ID`,
  `DOCLING_SERVE_URL` (PDF conversion).
- **Invariant single-runner-per-process** : les adapters mutent
  `os.environ["OLLAMA_HOST"]` dans leur constructeur. `main.py` n'instancie
  qu'**un** `OllamaProvider` et le passe aux deux runners. Ajouter un
  troisième runner : utilise le même provider, ne jamais en construire un
  second avec un host différent.
