"""Le worker de sonde : boucle périodique + une itération testable isolément.

`Monitor.tick()` sonde tous les services *dus* (dont la dernière sonde dépasse leur
`interval_seconds`). `Monitor.last_run_at` sert à `/ready` (le worker est-il vivant ?).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from statuspage.config import Settings
from statuspage.observability import Metrics, correlation_id
from statuspage.probe import probe
from statuspage.repository import CheckRepository, ServiceRepository

logger = logging.getLogger("statuspage.monitor")


class Monitor:
    def __init__(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
        settings: Settings,
        metrics: Metrics,
        client: httpx.AsyncClient,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._metrics = metrics
        self._client = client
        self.last_run_at: datetime | None = None

    async def tick(self) -> int:
        """Une passe : sonde les services dus. Renvoie le nombre de sondes effectuées."""
        token = correlation_id.set(f"check-{uuid.uuid4().hex[:12]}")
        performed = 0
        try:
            now = datetime.now(UTC)
            async with self._session_factory() as session:
                services = await ServiceRepository(session).list_all()
                last_times = await CheckRepository(session).last_check_times()

            due = [
                svc
                for svc in services
                if (last := last_times.get(svc.id)) is None
                or (now - last).total_seconds() >= svc.interval_seconds
            ]
            for svc in due:
                await self._probe_one(svc.id, svc.name, svc.url, svc.expected_status)
                performed += 1
            self.last_run_at = datetime.now(UTC)
            return performed
        finally:
            correlation_id.reset(token)

    async def _probe_one(self, service_id: int, name: str, url: str, expected_status: int) -> None:
        result = await probe(self._client, url, expected_status=expected_status)
        async with self._session_factory() as session:
            await CheckRepository(session).add(
                service_id=service_id,
                up=result.up,
                status_code=result.status_code,
                latency_ms=result.latency_ms,
                error=result.error,
                checked_at=datetime.now(UTC),
            )
            await session.commit()
        self._metrics.record(name, up=result.up, latency_ms=result.latency_ms)
        logger.info(
            "sonde %s : %s (%.0f ms)", name, "up" if result.up else "down", result.latency_ms
        )

    async def run_forever(self) -> None:
        logger.info("worker de sonde démarré (tick %.1fs)", self._settings.worker_tick_seconds)
        try:
            while True:
                try:
                    await self.tick()
                except Exception:
                    logger.exception("erreur dans le worker de sonde")
                await asyncio.sleep(self._settings.worker_tick_seconds)
        except asyncio.CancelledError:
            logger.info("worker de sonde arrêté")
            raise
