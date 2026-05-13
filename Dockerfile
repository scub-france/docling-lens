# syntax=docker/dockerfile:1.7
#
# docling-lens — single-image deployment.
#
# Three stages:
#   1. frontend-builder — npm ci + vite build → /build/dist
#   2. python-builder   — pip install into /opt/venv with CPU-only torch
#   3. runtime          — slim base, only venv + backend src + dist copied
#
# Image targets:
#   - No post-startup downloads. Every Python dep + frontend asset is
#     baked in at build time.
#   - Ollama + docling-serve stay EXTERNAL. The container reaches them
#     over the network (configurable via env vars).
#   - One process: FastAPI serves both the API (/api/*) and the SPA (/).
#
# Build:
#   docker build -t docling-lens:latest .
#
# Run (assumes Ollama on the host, docling-serve already running):
#   docker run --rm -p 8001:8001 \
#     -e REASONING_ENABLED=true \
#     -e OLLAMA_HOST=http://host.docker.internal:11434 \
#     -e DOCLING_SERVE_URL=http://host.docker.internal:5001 \
#     --add-host=host.docker.internal:host-gateway \
#     docling-lens:latest
#
# Then open http://localhost:8001

# =============================================================================
# Stage 1 — frontend bundle
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install deps first (cached when package*.json don't change).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Then bring the rest of the source and build.
COPY frontend/ ./
RUN npm run build


# =============================================================================
# Stage 2 — Python venv with CPU-only torch
# =============================================================================
FROM python:3.12-slim AS python-builder

# Build-time tools needed for any wheel that ships native code. `--no-install-
# recommends` keeps the layer small; we drop the whole stage at the end so
# this growth is invisible to the runtime image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Isolate everything into a venv we can copy verbatim into stage 3.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt ./

# Torch CPU wheels are ~200 MB smaller than the default CUDA build and we
# don't run inference in-process — Ollama hosts the models. We pull torch
# (a transitive dep of mellea) from the official CPU index, then the rest
# from PyPI normally.
RUN pip install --upgrade pip wheel \
 && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt \
 && find /opt/venv -type d -name __pycache__ -prune -exec rm -rf {} + \
 && find /opt/venv -type d -name tests -prune -exec rm -rf {} +


# =============================================================================
# Stage 3 — runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# Single non-root user; restricted shell.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SPA_DIR=/app/static \
    HOST=0.0.0.0 \
    PORT=8001

# venv from stage 2 (already trimmed of __pycache__ / package tests).
COPY --from=python-builder --chown=app:app /opt/venv /opt/venv

# Backend source — `.dockerignore` keeps tests, CLAUDE.md, pytest config out.
COPY --chown=app:app backend/ /app/backend/

# Built SPA from stage 1 — served by FastAPI via `SPA_DIR`.
COPY --from=frontend-builder --chown=app:app /build/dist /app/static

USER app
WORKDIR /app/backend

EXPOSE 8001

# `uvicorn[standard]` brings httptools + uvloop for prod-grade perf.
# `--proxy-headers` is sensible default behind any reverse proxy.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
