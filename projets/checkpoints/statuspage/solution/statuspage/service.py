"""Couche métier : création de services/incidents, agrégation du statut."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from statuspage.config import Settings
from statuspage.errors import (
    IncidentNotFoundError,
    InvalidTransitionError,
    ServiceNotFoundError,
)
from statuspage.models import CheckRow, IncidentRow, ServiceRow
from statuspage.repository import CheckRepository, IncidentRepository, ServiceRepository
from statuspage.schemas import (
    CheckPage,
    CheckRead,
    IncidentRead,
    ServiceRead,
    ServiceStatus,
    StatusSummary,
)

_RANK = {
    ServiceStatus.operational: 0,
    ServiceStatus.unknown: 1,
    ServiceStatus.degraded: 2,
    ServiceStatus.outage: 3,
}


def _status_from_recent(recent: list[CheckRow], *, outage_threshold: int) -> ServiceStatus:
    if not recent:
        return ServiceStatus.unknown
    if recent[0].up:
        return ServiceStatus.operational
    # `recent` est trié du plus récent au plus ancien
    consecutive_failures = 0
    for check in recent:
        if check.up:
            break
        consecutive_failures += 1
    if consecutive_failures >= outage_threshold:
        return ServiceStatus.outage
    return ServiceStatus.degraded


class StatusService:
    def __init__(
        self,
        services: ServiceRepository,
        checks: CheckRepository,
        incidents: IncidentRepository,
        settings: Settings,
    ) -> None:
        self._services = services
        self._checks = checks
        self._incidents = incidents
        self._settings = settings

    # --- services ------------------------------------------------------
    async def create_service(
        self, *, name: str, url: str, interval_seconds: int, expected_status: int
    ) -> ServiceRead:
        row = await self._services.create(
            name=name, url=url, interval_seconds=interval_seconds, expected_status=expected_status
        )
        return await self._to_read(row)

    async def get_service(self, service_id: int) -> ServiceRead:
        row = await self._require_service(service_id)
        return await self._to_read(row)

    async def list_services(self) -> list[ServiceRead]:
        return [await self._to_read(row) for row in await self._services.list_all()]

    async def delete_service(self, service_id: int) -> None:
        if not await self._services.delete(service_id):
            raise ServiceNotFoundError(service_id)

    async def history(
        self, service_id: int, *, since: datetime | None, limit: int, offset: int
    ) -> CheckPage:
        await self._require_service(service_id)
        rows, total = await self._checks.history(
            service_id, since=since, limit=limit, offset=offset
        )
        return CheckPage(
            items=[CheckRead.model_validate(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    # --- incidents ----------------------------------------------------
    async def open_incident(self, *, title: str, body: str) -> IncidentRead:
        return IncidentRead.model_validate(await self._incidents.create(title=title, body=body))

    async def update_incident(
        self,
        incident_id: int,
        *,
        title: str | None,
        body: str | None,
        status: str | None,
    ) -> IncidentRead:
        row = await self._incidents.get(incident_id)
        if row is None:
            raise IncidentNotFoundError(incident_id)
        if title is not None:
            row.title = title
        if body is not None:
            row.body = body
        if status is not None:
            self._apply_transition(row, status)
        return IncidentRead.model_validate(row)

    @staticmethod
    def _apply_transition(row: IncidentRow, target: str) -> None:
        if row.status == "resolved" and target != "resolved":
            raise InvalidTransitionError("un incident résolu ne se rouvre pas")
        row.status = target
        row.resolved_at = datetime.now(UTC) if target == "resolved" else None

    # --- agrégat ----------------------------------------------------
    async def status_summary(self) -> StatusSummary:
        services = await self.list_services()
        incidents = [IncidentRead.model_validate(r) for r in await self._incidents.list_active()]
        overall = ServiceStatus.operational
        for svc in services:
            if _RANK[svc.current_status] > _RANK[overall]:
                overall = svc.current_status
        if not services:
            overall = ServiceStatus.unknown
        return StatusSummary(
            overall=overall,
            services=services,
            active_incidents=incidents,
            generated_at=datetime.now(UTC),
        )

    # --- privé ----------------------------------------------------
    async def _require_service(self, service_id: int) -> ServiceRow:
        row = await self._services.get(service_id)
        if row is None:
            raise ServiceNotFoundError(service_id)
        return row

    async def _to_read(self, row: ServiceRow) -> ServiceRead:
        recent = await self._checks.recent(row.id, limit=self._settings.outage_consecutive_failures)
        window_start = datetime.now(UTC) - timedelta(hours=self._settings.uptime_window_hours)
        uptime = await self._checks.uptime_ratio(row.id, since=window_start)
        return ServiceRead(
            id=row.id,
            name=row.name,
            url=row.url,
            interval_seconds=row.interval_seconds,
            expected_status=row.expected_status,
            current_status=_status_from_recent(
                recent, outage_threshold=self._settings.outage_consecutive_failures
            ),
            uptime_ratio=uptime,
            last_checked_at=recent[0].checked_at if recent else None,
        )
