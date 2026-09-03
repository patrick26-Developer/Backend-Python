"""Métriques Prometheus (méthode RED : Rate, Errors, Duration).

Le label `path` est **toujours le template de route** (`/tasks/{task_id}`), jamais
l'URL concrète — sinon une série par identifiant → explosion de cardinalité.
"""

from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUESTS = Counter(
    "http_requests_total",
    "Nombre de requêtes HTTP",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latence des requêtes HTTP",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
IN_PROGRESS = Counter(
    "http_requests_in_progress_total",
    "Requêtes reçues (compteur d'entrée)",
    ["method"],
)


def _route_template(request: Request) -> str:
    """Le pattern de la route (`/tasks/{task_id}`), pas l'URL (`/tasks/42`)."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        IN_PROGRESS.labels(request.method).inc()
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = _route_template(request)
            elapsed = time.perf_counter() - start
            REQUESTS.labels(request.method, path, str(status_code)).inc()
            LATENCY.labels(request.method, path).observe(elapsed)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
