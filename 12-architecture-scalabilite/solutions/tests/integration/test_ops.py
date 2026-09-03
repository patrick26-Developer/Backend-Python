"""Tests des routes d'exploitation : /health, /ready, /metrics (Module 09)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from taskman.api.deps import get_session
from tests.factories import task_payload


# --- liveness --------------------------------------------------
async def test_health_is_always_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- readiness ------------------------------------------------
async def test_ready_ok_when_dependencies_up(client: AsyncClient) -> None:
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"database": "ok", "cache": "ok"}


async def test_ready_503_when_database_down(app: FastAPI) -> None:
    class BrokenSession:
        async def execute(self, *_a: object, **_k: object) -> None:
            raise RuntimeError("db down")

    async def _broken() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_session] = _broken
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["checks"]["database"] == "fail"
    finally:
        app.dependency_overrides.pop(get_session, None)


# --- métriques ------------------------------------------------
async def test_metrics_endpoint_exposes_series(client: AsyncClient) -> None:
    await client.get("/health")  # génère au moins une observation
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text


async def test_metrics_path_label_is_route_template(member_client: AsyncClient) -> None:
    pid = (await member_client.post("/v1/projects", json={"name": "P"})).json()["id"]
    tid = (await member_client.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]
    await member_client.get(f"/v1/tasks/{tid}")

    metrics = (await member_client.get("/metrics")).text
    # le label doit être le PATTERN de route, jamais l'URL concrète (cardinalité bornée)
    assert 'path="/tasks/{task_id}"' in metrics
    assert f'path="/tasks/{tid}"' not in metrics
    assert f"/tasks/{tid}" not in metrics


async def test_metrics_not_in_openapi(client: AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert "/metrics" not in paths  # include_in_schema=False


@pytest.mark.parametrize("route", ["/health", "/ready", "/metrics"])
async def test_ops_routes_need_no_auth(client: AsyncClient, route: str) -> None:
    assert (await client.get(route)).status_code in (200, 503)
