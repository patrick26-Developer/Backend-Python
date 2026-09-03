"""*Outbox pattern* (Module 12).

Écrire l'événement **dans la même transaction** que la donnée résout le problème
du « double write » : on ne peut pas avoir la tâche committée mais l'événement
perdu (ou l'inverse).

Un *drain* (`drain_outbox`) — appelé par un worker périodique — lit les lignes non
publiées, les publie, pose `published_at`. Garantie *at-least-once* → les
consommateurs doivent être **idempotents**.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taskman.db.models import OutboxRow
from taskman.domain.events import DomainEvent, EventPublisher


class OutboxRepository(Protocol):
    async def add(self, event: DomainEvent) -> None: ...

    async def list_unpublished(self, *, limit: int) -> list[tuple[int, DomainEvent]]: ...

    async def mark_published(self, ids: list[int]) -> None: ...


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: DomainEvent) -> None:
        self._session.add(OutboxRow(event_type=event.type, payload=event.payload))
        await self._session.flush()

    async def list_unpublished(self, *, limit: int) -> list[tuple[int, DomainEvent]]:
        rows = (
            await self._session.scalars(
                select(OutboxRow)
                .where(OutboxRow.published_at.is_(None))
                .order_by(OutboxRow.id)
                .limit(limit)
            )
        ).all()
        return [(r.id, DomainEvent(type=r.event_type, payload=r.payload)) for r in rows]

    async def mark_published(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(
            update(OutboxRow).where(OutboxRow.id.in_(ids)).values(published_at=datetime.now(UTC))
        )
        await self._session.flush()


class InMemoryOutboxRepository:
    def __init__(self) -> None:
        self._rows: list[tuple[int, DomainEvent, bool]] = []
        self._seq = 0

    async def add(self, event: DomainEvent) -> None:
        self._seq += 1
        self._rows.append((self._seq, event, False))

    async def list_unpublished(self, *, limit: int) -> list[tuple[int, DomainEvent]]:
        return [(i, e) for i, e, done in self._rows if not done][:limit]

    async def mark_published(self, ids: list[int]) -> None:
        marked = set(ids)
        self._rows = [(i, e, done or i in marked) for i, e, done in self._rows]


async def drain_outbox(
    outbox: OutboxRepository,
    publisher: EventPublisher,
    session_commit: object,
    *,
    batch: int = 100,
) -> int:
    """Publie les événements en attente. Renvoie le nombre publié.
    `session_commit` : un objet avec `commit()` (la session / UnitOfWork)."""
    pending = await outbox.list_unpublished(limit=batch)
    for _id, event in pending:
        await publisher.publish(event)
    await outbox.mark_published([i for i, _ in pending])
    await session_commit.commit()  # type: ignore[attr-defined]
    return len(pending)
