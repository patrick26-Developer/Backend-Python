"""Idempotence des écritures via l'en-tête `Idempotency-Key` (Module 12).

Un client qui *retry* un `POST` après une coupure réseau ne doit pas créer deux
ressources. On stocke `(clé → réponse)` : le rejeu renvoie la réponse d'origine
sans re-traiter.

Middleware : n'agit que sur `POST`/`PATCH` **avec** l'en-tête. Stockage dans le
cache (`InMemoryCache` / Redis), TTL 24 h.
"""

from __future__ import annotations

import json

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_METHODS = {"POST", "PATCH"}
_TTL = 24 * 3600
_MAX_STORED_BODY = 256 * 1024  # on ne rejoue pas des réponses énormes


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _METHODS:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        key = request.headers.get("idempotency-key")
        if not key:
            await self.app(scope, receive, send)
            return

        cache = scope["app"].state.cache
        cache_key = f"idem:{scope['method']}:{request.url.path}:{key}"

        stored = await cache.get(cache_key)
        if stored is not None:
            data = json.loads(stored)
            await send(
                {
                    "type": "http.response.start",
                    "status": data["status"],
                    "headers": [
                        *[(k.encode(), v.encode()) for k, v in data["headers"].items()],
                        (b"idempotent-replay", b"true"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": data["body"].encode()})
            return

        # 1er appel : on exécute et on capture la réponse
        status_code = 500
        headers: dict[str, str] = {}
        chunks: list[bytes] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers.update({k.decode(): v.decode() for k, v in message.get("headers", [])})
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, send_wrapper)

        body = b"".join(chunks)
        # on ne mémorise que les succès de taille raisonnable
        if 200 <= status_code < 300 and len(body) <= _MAX_STORED_BODY:
            keep = {k: v for k, v in headers.items() if k.lower() in {"content-type", "location"}}
            await cache.set(
                cache_key,
                json.dumps({"status": status_code, "headers": keep, "body": body.decode()}),
                ttl=_TTL,
            )
