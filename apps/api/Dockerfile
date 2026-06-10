# ============================================================================
# API FastAPI — build multi-stage (imagem final enxuta, usuário não-root)
# Build:  docker build -t rastreio-api apps/api
# Run:    docker run --env-file apps/api/.env -p 8000:8000 rastreio-api
# ============================================================================

# --- Stage 1: resolve dependências com uv (ADR-010) -------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

# Camada de dependências separada do código: cache de build eficiente
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Código da aplicação + migrations (o deploy roda `alembic upgrade head`)
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

# --- Stage 2: runtime mínimo -------------------------------------------------
FROM python:3.12-slim-bookworm
WORKDIR /app

# Usuário não-root (princípio do menor privilégio)
RUN groupadd --system api && useradd --system --gid api --no-create-home api

COPY --from=builder --chown=api:api /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER api
EXPOSE 8000

# Liveness do container — usa stdlib (a imagem slim não tem curl)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
