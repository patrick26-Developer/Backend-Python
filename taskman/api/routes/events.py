"""Flux temps réel (SSE) — Module 12.

`GET /v1/events` : le serveur pousse les événements de domaine au client (une
connexion HTTP qui ne se ferme pas). Le navigateur gère la reconnexion tout seul.

Fan-out multi-instance : via Redis pub/sub (voir `taskman/realtime.py`).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from taskman.api.deps import CurrentUser, EventPublisherDep

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def stream_events(
    request: Request,
    _user: CurrentUser,
    publisher: EventPublisherDep,
) -> EventSourceResponse:
    async def _generator() -> AsyncIterator[dict[str, str]]:
        yield {"event": "connected", "data": "{}"}  # confirme l'établissement
        subscription = publisher.subscribe()
        try:
            async for event in subscription:
                if await request.is_disconnected():
                    break
                yield {"event": event.type, "data": event.model_dump_json()}
        finally:
            with contextlib.suppress(Exception):
                await subscription.aclose()

    return EventSourceResponse(_generator(), ping=15)
