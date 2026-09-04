"""Accès données — le seul code qui parle SQL."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from statuspage.errors import ServiceNameTakenError
from statuspage.models import CheckRow, IncidentRow, ServiceRow


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, name: str, url: str, interval_seconds: int, expected_status: int
    ) -> ServiceRow:
        row = ServiceRow(
            name=name, url=url, interval_seconds=interval_seconds, expected_status=expected_status
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ServiceNameTakenError(name) from exc
        return row

    async def get(self, service_id: int) -> ServiceRow | None:
        return (
            await self._session.scalars(select(ServiceRow).where(ServiceRow.id == service_id))
        ).one_or_none()

    async def list_all(self) -> list[ServiceRow]:
        return list(
            (await self._session.scalars(select(ServiceRow).order_by(ServiceRow.name))).all()
        )

    async def delete(self, service_id: int) -> bool:
        row = await self.get(service_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class CheckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        service_id: int,
        up: bool,
        status_code: int | None,
        latency_ms: float,
        error: str | None,
        checked_at: datetime,
    ) -> CheckRow:
        row = CheckRow(
            service_id=service_id,
            up=up,
            status_code=status_code,
            latency_ms=latency_ms,
            error=error,
            checked_at=checked_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def recent(self, service_id: int, *, limit: int) -> list[CheckRow]:
        return list(
            (
                await self._session.scalars(
                    select(CheckRow)
                    .where(CheckRow.service_id == service_id)
                    .order_by(CheckRow.checked_at.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def history(
        self, service_id: int, *, since: datetime | None, limit: int, offset: int
    ) -> tuple[list[CheckRow], int]:
        base = select(CheckRow).where(CheckRow.service_id == service_id)
        if since is not None:
            base = base.where(CheckRow.checked_at >= since)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.scalars(
                base.order_by(CheckRow.checked_at.desc()).limit(limit).offset(offset)
            )
        ).all()
        return list(rows), int(total or 0)

    async def uptime_ratio(self, service_id: int, *, since: datetime) -> float | None:
        total = await self._session.scalar(
            select(func.count())
            .select_from(CheckRow)
            .where(CheckRow.service_id == service_id, CheckRow.checked_at >= since)
        )
        if not total:
            return None
        up = await self._session.scalar(
            select(func.count())
            .select_from(CheckRow)
            .where(
                CheckRow.service_id == service_id,
                CheckRow.checked_at >= since,
                CheckRow.up.is_(True),
            )
        )
        return round((up or 0) / total, 4)

    async def last_check_times(self) -> dict[int, datetime]:
        """`service_id -> horodatage de la dernière sonde` (aware UTC)."""
        rows = await self._session.execute(
            select(CheckRow.service_id, func.max(CheckRow.checked_at)).group_by(CheckRow.service_id)
        )
        result: dict[int, datetime] = {}
        for service_id, last_at in rows:
            if last_at is not None:
                result[service_id] = last_at if last_at.tzinfo else last_at.replace(tzinfo=UTC)
        return result


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, title: str, body: str) -> IncidentRow:
        row = IncidentRow(title=title, body=body, status="investigating")
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, incident_id: int) -> IncidentRow | None:
        return (
            await self._session.scalars(select(IncidentRow).where(IncidentRow.id == incident_id))
        ).one_or_none()

    async def list_active(self) -> list[IncidentRow]:
        return list(
            (
                await self._session.scalars(
                    select(IncidentRow)
                    .where(IncidentRow.status != "resolved")
                    .order_by(IncidentRow.created_at.desc())
                )
            ).all()
        )
