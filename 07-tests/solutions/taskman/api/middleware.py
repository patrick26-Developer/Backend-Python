"""Middleware ASGI : identifiant de requête + journal d'accès + latence.

Pour chaque requête :
1. récupère `X-Request-ID` de l'entête, ou en génère un ;
2. le publie dans le `ContextVar` (→ tous les logs de la requête le porteront) ;
3. mesure la durée ;
4. ré-émet `X-Request-ID` dans la réponse ;
5. loggue une ligne d'accès (même si la requête a levé une exception).

Écrit comme un middleware ASGI « pur » (et non `BaseHTTPMiddleware`) : plus léger,
compatible streaming et *background tasks*.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from taskman.core.context import request_id_var

_logger = logging.getLogger("taskman.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _logger.info(
                "%s %s -> %s",
                request.method,
                request.url.path,
                status_code,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            )
            request_id_var.reset(token)
