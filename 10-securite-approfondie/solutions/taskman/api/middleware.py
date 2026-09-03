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


# --------------------------------------------------------------------------- #
#  Module 10 : durcissement                                                     #
# --------------------------------------------------------------------------- #
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")

_SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
)
_CSP = b"default-src 'none'; frame-ancestors 'none'"
_HSTS = b"max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Ajoute les en-têtes de sécurité à chaque réponse.

    - CSP stricte, sauf sur `/docs` (Swagger UI charge du JS depuis un CDN) ;
    - HSTS seulement en production (inutile — voire gênant — en HTTP local).
    """

    def __init__(self, app: ASGIApp, *, is_production: bool) -> None:
        self.app = app
        self.is_production = is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_docs = any(path.startswith(p) for p in _DOCS_PATHS)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(_SECURITY_HEADERS)
                if not is_docs:
                    headers.append((b"content-security-policy", _CSP))
                if self.is_production:
                    headers.append((b"strict-transport-security", _HSTS))
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Rejette (413) les requêtes dont `Content-Length` dépasse la limite.

    Défense simple contre l'*unrestricted resource consumption* (OWASP API #4).
    Un client sans `Content-Length` (corps *chunked*) passe cette barrière —
    Uvicorn a sa propre limite, et la validation Pydantic borne le reste.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                    await self._reject(send)
                    return
        await self.app(scope, receive, send)

    async def _reject(self, send: Send) -> None:
        body = b'{"title":"Corps trop volumineux","status":413,"code":"payload_too_large"}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/problem+json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
