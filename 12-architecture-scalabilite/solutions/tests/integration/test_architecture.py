"""Tests du Module 12 : outbox, idempotence, versionnage, SSE."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from taskman.db.models import OutboxRow
from taskman.domain.events import DomainEvent
from taskman.outbox import InMemoryOutboxRepository, drain_outbox
from taskman.realtime import InMemoryEventPublisher
from tests.factories import task_payload


async def _project(client: AsyncClient) -> int:
    return (await client.post("/v1/projects", json={"name": "P"})).json()["id"]


# --- versionnage --------------------------------------------
async def test_v1_and_v2_coexist(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    tid = (await member_client.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]

    v1 = (await member_client.get(f"/v1/tasks/{tid}")).json()
    v2 = (await member_client.get(f"/v2/tasks/{tid}")).json()

    assert "is_overdue" in v1 and "checklist" in v1  # contrat v1
    assert "overdue" in v2 and "checklist_total" in v2  # contrat v2 (change)
    assert "is_overdue" not in v2


async def test_unversioned_business_path_is_404(client: AsyncClient) -> None:
    assert (await client.get("/tasks")).status_code == 404  # tout est sous /v1


async def test_ops_routes_stay_unversioned(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200


# --- outbox (unité) ---------------------------------------
async def test_outbox_drain_publishes_and_marks() -> None:
    outbox = InMemoryOutboxRepository()
    publisher = InMemoryEventPublisher()
    received: list[DomainEvent] = []

    async def _collect() -> None:
        async for event in publisher.subscribe():
            received.append(event)

    task = asyncio.create_task(_collect())
    await asyncio.sleep(0)

    await outbox.add(DomainEvent(type="task.completed", payload={"task_id": 1}))
    await outbox.add(DomainEvent(type="task.completed", payload={"task_id": 2}))

    class _Uow:
        async def commit(self) -> None: ...

    published = await drain_outbox(outbox, publisher, _Uow())
    await asyncio.sleep(0.01)
    task.cancel()

    assert published == 2
    assert [e.payload["task_id"] for e in received] == [1, 2]
    # rien ne reste à publier
    assert await outbox.list_unpublished(limit=10) == []


async def test_complete_writes_event_in_same_transaction(
    member_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    pid = await _project(member_client)
    tid = (await member_client.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]
    await member_client.post(f"/v1/tasks/{tid}/complete")

    async with session_factory() as s:
        rows = (await s.scalars(select(OutboxRow))).all()
    assert len(rows) == 1
    assert rows[0].event_type == "task.completed"
    assert rows[0].payload["task_id"] == tid
    assert rows[0].published_at is None  # pas encore drainé vers le broker


# --- idempotence ------------------------------------------
async def test_idempotency_key_replays_response(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    body = task_payload(project_id=pid, title="idempotent")
    key = {"Idempotency-Key": "abc-123"}

    r1 = await member_client.post("/v1/tasks", json=body, headers=key)
    r2 = await member_client.post("/v1/tasks", json=body, headers=key)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # MÊME ressource, pas deux
    assert r2.headers.get("idempotent-replay") == "true"

    total = (await member_client.get("/v1/tasks")).json()["total"]
    assert total == 1


async def test_different_key_creates_new_resource(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    body = task_payload(project_id=pid)
    await member_client.post("/v1/tasks", json=body, headers={"Idempotency-Key": "k1"})
    await member_client.post("/v1/tasks", json=body, headers={"Idempotency-Key": "k2"})
    assert (await member_client.get("/v1/tasks")).json()["total"] == 2


async def test_no_key_no_dedup(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    body = task_payload(project_id=pid)
    await member_client.post("/v1/tasks", json=body)
    await member_client.post("/v1/tasks", json=body)
    assert (await member_client.get("/v1/tasks")).json()["total"] == 2


# --- SSE --------------------------------------------------
@pytest.mark.slow
async def test_sse_stream_delivers_events(app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport

    async def _authed() -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await c.post(
            "/v1/auth/register", json={"email": "sse@x.co", "password": "password-de-test-12345"}
        )
        r = await c.post(
            "/v1/auth/login", data={"username": "sse@x.co", "password": "password-de-test-12345"}
        )
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        return c

    listener = await _authed()
    actor = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    actor.headers.update(listener.headers)
    try:
        pid = (await actor.post("/v1/projects", json={"name": "P"})).json()["id"]
        tid = (await actor.post("/v1/tasks", json=task_payload(project_id=pid))).json()["id"]

        events: list[str] = []
        async with listener.stream("GET", "/v1/events") as resp:
            assert resp.headers["content-type"].startswith("text/event-stream")

            async def _read() -> None:
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        events.append(line.split(":", 1)[1].strip())
                    if "task.completed" in events:
                        break

            reader = asyncio.create_task(_read())
            await asyncio.sleep(0.05)
            await actor.post(f"/v1/tasks/{tid}/complete")
            await asyncio.wait_for(reader, timeout=3)

        assert "connected" in events
        assert "task.completed" in events
    finally:
        await listener.aclose()
        await actor.aclose()
