"""Tests d'intégration : endpoints, statuts agrégés, exploitation (/health, /ready, /metrics)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from statuspage.models import CheckRow


async def _svc(client: httpx.AsyncClient, **over: object) -> dict:
    body: dict[str, object] = {"name": "API", "url": "https://api.example", "interval_seconds": 30}
    body.update(over)
    r = await client.post("/services", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _record(factory: async_sessionmaker[AsyncSession], service_id: int, *ups: bool) -> None:
    """Insère des sondes, de la plus ancienne (index 0) à la plus récente."""
    async with factory() as session:
        now = datetime.now(UTC)
        for i, up in enumerate(ups):
            session.add(
                CheckRow(
                    service_id=service_id,
                    up=up,
                    status_code=200 if up else 503,
                    latency_ms=12.0,
                    error=None if up else "down",
                    checked_at=now - timedelta(seconds=(len(ups) - i)),
                )
            )
        await session.commit()


# --- services -------------------------------------------------------
async def test_create_service_location_header(client: httpx.AsyncClient) -> None:
    r = await client.post("/services", json={"name": "X", "url": "https://x.example"})
    assert r.status_code == 201
    assert r.headers["location"] == f"/services/{r.json()['id']}"


async def test_duplicate_name_is_409(client: httpx.AsyncClient) -> None:
    await _svc(client, name="dup")
    r = await client.post("/services", json={"name": "dup", "url": "https://other.example"})
    assert r.status_code == 409


async def test_invalid_url_is_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/services", json={"name": "Y", "url": "not-a-url"})
    assert r.status_code == 422


async def test_new_service_status_is_unknown(client: httpx.AsyncClient) -> None:
    created = await _svc(client)
    body = (await client.get(f"/services/{created['id']}")).json()
    assert body["current_status"] == "unknown"
    assert body["uptime_ratio"] is None
    assert body["last_checked_at"] is None


async def test_get_missing_service_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/services/999")).status_code == 404


async def test_delete_service(client: httpx.AsyncClient) -> None:
    created = await _svc(client)
    assert (await client.delete(f"/services/{created['id']}")).status_code == 204
    assert (await client.get(f"/services/{created['id']}")).status_code == 404


# --- statut agrégé ------------------------------------------------
async def test_status_reflects_recent_checks(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    ok = await _svc(client, name="ok", url="https://ok.example")
    deg = await _svc(client, name="deg", url="https://deg.example")
    down = await _svc(client, name="down", url="https://down.example")

    await _record(session_factory, ok["id"], True, True, True)
    await _record(session_factory, deg["id"], True, False)  # 1 seul échec récent
    await _record(session_factory, down["id"], False, False, False)  # 3 échecs consécutifs

    services = {s["name"]: s for s in (await client.get("/services")).json()}
    assert services["ok"]["current_status"] == "operational"
    assert services["deg"]["current_status"] == "degraded"
    assert services["down"]["current_status"] == "outage"
    assert services["ok"]["uptime_ratio"] == 1.0

    summary = (await client.get("/status")).json()
    assert summary["overall"] == "outage"  # le pire l'emporte


async def test_history_endpoint(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _svc(client)
    await _record(session_factory, created["id"], True, False, True, False, True)

    page = (await client.get(f"/services/{created['id']}/history", params={"limit": 2})).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2

    since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    recent = (
        await client.get(f"/services/{created['id']}/history", params={"since": since})
    ).json()
    assert recent["total"] <= 5


# --- incidents --------------------------------------------------
async def test_incident_lifecycle(client: httpx.AsyncClient) -> None:
    created = (
        await client.post("/incidents", json={"title": "Panne DB", "body": "on regarde"})
    ).json()
    assert created["status"] == "investigating"
    assert created["resolved_at"] is None

    resolved = (
        await client.patch(f"/incidents/{created['id']}", json={"status": "resolved"})
    ).json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None

    reopen = await client.patch(f"/incidents/{created['id']}", json={"status": "investigating"})
    assert reopen.status_code == 409


async def test_patch_unknown_incident_404(client: httpx.AsyncClient) -> None:
    assert (await client.patch("/incidents/999", json={"title": "x"})).status_code == 404


async def test_active_incidents_in_status(client: httpx.AsyncClient) -> None:
    await client.post("/incidents", json={"title": "actif"})
    done = (await client.post("/incidents", json={"title": "clos"})).json()
    await client.patch(f"/incidents/{done['id']}", json={"status": "resolved"})

    titles = [i["title"] for i in (await client.get("/status")).json()["active_incidents"]]
    assert titles == ["actif"]


# --- exploitation -----------------------------------------------
async def test_health_is_ok(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_ready_ok_when_db_up_and_worker_disabled(client: httpx.AsyncClient) -> None:
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_ready_503_when_worker_stale(
    client: httpx.AsyncClient,
    app,
    settings,  # type: ignore[no-untyped-def]
) -> None:
    settings.worker_enabled = True
    settings.ready_max_worker_staleness_seconds = 0.01
    app.state.monitor.last_run_at = datetime.now(UTC) - timedelta(seconds=10)

    r = await client.get("/ready")
    assert r.status_code == 503
    assert "worker-stale" in r.json()["problems"]


async def test_ready_503_when_worker_never_ran(
    client: httpx.AsyncClient,
    app,
    settings,  # type: ignore[no-untyped-def]
) -> None:
    settings.worker_enabled = True
    app.state.monitor.last_run_at = None
    r = await client.get("/ready")
    assert r.status_code == 503
    assert "worker-not-started" in r.json()["problems"]


async def test_metrics_endpoint_exposes_prometheus_text(client: httpx.AsyncClient) -> None:
    await _svc(client, name="m")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "statuspage_check_latency_seconds" in r.text


async def test_request_id_header_roundtrip(client: httpx.AsyncClient) -> None:
    r = await client.get("/health", headers={"x-request-id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    generated = (await client.get("/health")).headers["x-request-id"]
    assert generated.startswith("req-")


async def test_openapi(client: httpx.AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    for p in ("/services", "/services/{service_id}", "/status", "/incidents"):
        assert p in paths
