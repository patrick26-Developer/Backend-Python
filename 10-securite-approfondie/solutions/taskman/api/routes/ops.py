"""Routes d'exploitation : liveness, readiness, métriques.

- `/health`  : le process répond (liveness). Toujours 200 tant qu'il tourne.
- `/ready`   : les dépendances critiques (DB, cache) répondent. 503 sinon.
- `/metrics` : les séries Prometheus (scrapées par le serveur de métriques).

Non authentifiées (Prometheus/Kubernetes doivent y accéder) — mais à ne pas
exposer publiquement (réseau interne / proxy).
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from taskman.api.deps import CacheDep, SessionDep
from taskman.observability.metrics import metrics_response

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: SessionDep, cache: CacheDep) -> JSONResponse:
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # panne quelconque -> "fail"
        checks["database"] = "fail"

    try:
        await cache.set("_readiness_probe", "1", ttl=5)
        checks["cache"] = "ok"
    except Exception:  # idem
        checks["cache"] = "fail"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ready" if healthy else "degraded", "checks": checks},
        status_code=200 if healthy else 503,
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()
