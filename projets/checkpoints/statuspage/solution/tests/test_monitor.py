"""Le worker de sonde : `tick()` sonde les services dus, enregistre, alimente les métriques."""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from statuspage.config import Settings
from statuspage.models import CheckRow, ServiceRow
from statuspage.monitor import Monitor
from statuspage.observability import Metrics


async def _add_service(factory: async_sessionmaker[AsyncSession], **over: object) -> int:
    async with factory() as session:
        row = ServiceRow(
            name=str(over.get("name", "svc")),
            url=str(over.get("url", "https://svc.example")),
            interval_seconds=int(over.get("interval_seconds", 60)),  # type: ignore[call-overload]
            expected_status=int(over.get("expected_status", 200)),  # type: ignore[call-overload]
        )
        session.add(row)
        await session.commit()
        return row.id


async def test_tick_probes_due_services_and_records(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, metrics: Metrics
) -> None:
    sid = await _add_service(session_factory)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    monitor = Monitor(session_factory, settings, metrics, client)

    performed = await monitor.tick()
    assert performed == 1
    assert monitor.last_run_at is not None

    async with session_factory() as session:
        checks = (await session.scalars(select(CheckRow).where(CheckRow.service_id == sid))).all()
    assert len(checks) == 1 and checks[0].up is True

    # métrique alimentée
    assert b"statuspage_checks_total" in metrics.render()[0]


async def test_tick_skips_recently_checked_service(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, metrics: Metrics
) -> None:
    await _add_service(session_factory, interval_seconds=3600)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    monitor = Monitor(session_factory, settings, metrics, client)

    assert await monitor.tick() == 1  # 1re fois : dû
    assert await monitor.tick() == 0  # tout de suite après : pas encore dû (intervalle 1h)


async def test_tick_records_failures_for_metrics(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, metrics: Metrics
) -> None:
    await _add_service(session_factory, name="flaky")
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(500)))
    monitor = Monitor(session_factory, settings, metrics, client)
    await monitor.tick()

    body = metrics.render()[0]
    assert b'statuspage_check_failures_total{service="flaky"} 1.0' in body
