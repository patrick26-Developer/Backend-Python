# syntax=docker/dockerfile:1
# Image de production de taskman. Multi-stage, non-root, ~180 Mo.
# Build :  docker build -t taskman:local .
# Run   :  docker run --rm -p 8000:8000 --env-file .env taskman:local

# ---------------------------------------------------------------------------
# Étage 1 — build : installe les dépendances dans un venv isolé
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# On copie d'abord SEULEMENT le manifeste -> le layer d'install est mis en cache
# tant que les dépendances ne changent pas.
COPY pyproject.toml README.md ./
COPY taskman/__init__.py taskman/__init__.py
RUN pip install .

# ---------------------------------------------------------------------------
# Étage 2 — runtime : minimal, non-root
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH" \
    PYTHONPATH=/app \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app

COPY --from=builder /venv /venv

WORKDIR /app
COPY taskman/ ./taskman/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status == 200 else sys.exit(1)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["fastapi", "run", "taskman/main.py", "--host", "0.0.0.0", "--port", "8000"]
