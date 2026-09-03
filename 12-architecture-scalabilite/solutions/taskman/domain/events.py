"""Événements de domaine (Module 12).

Un événement = un **fait métier passé** (`task.completed`). Immuable. Émis dans la
transaction (outbox), publié ensuite par un worker.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Protocol

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    model_config = {"frozen": True}

    type: str = Field(examples=["task.completed"])
    payload: dict[str, Any]


class EventPublisher(Protocol):
    """Diffusion des événements aux abonnés temps réel (SSE)."""

    async def publish(self, event: DomainEvent) -> None: ...

    # `def` (pas `async def`) : une fonction génératrice async a ce type.
    def subscribe(self) -> AsyncGenerator[DomainEvent, None]: ...
