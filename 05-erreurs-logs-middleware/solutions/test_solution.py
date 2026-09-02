"""Tests de la solution du Module 05 — format d'erreur unifié, request-id, logs."""

from __future__ import annotations

import json
import logging

import pytest
from httpx import AsyncClient

from taskman.core.context import request_id_var
from taskman.core.exceptions import DomainError, NotFoundError, TaskNotFoundError
from taskman.core.logging import JsonFormatter
from taskman.repositories import InMemoryTaskRepository, NullUnitOfWork
from taskman.services import TaskService


async def _project(client: AsyncClient) -> int:
    r = await client.post("/projects", json={"name": "P"})
    return r.json()["id"]


# --- exceptions métier -----------------------------------------
def test_exception_hierarchy() -> None:
    exc = TaskNotFoundError(7)
    assert isinstance(exc, NotFoundError) and isinstance(exc, DomainError)
    assert exc.status_code == 404
    assert exc.code == "task_not_found"
    assert exc.task_id == 7


async def test_service_raises_not_found() -> None:
    service = TaskService(InMemoryTaskRepository(), NullUnitOfWork())
    with pytest.raises(TaskNotFoundError):
        await service.get(123)


# --- format d'erreur unifié (RFC 9457) -----------------------
async def test_not_found_problem_details(client: AsyncClient) -> None:
    resp = await client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["code"] == "task_not_found"
    assert body["instance"] == "/tasks/999"
    assert "request_id" in body


async def test_validation_same_format(client: AsyncClient) -> None:
    pid = await _project(client)
    resp = await client.post("/tasks", json={"title": "", "project_id": pid})
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


async def test_integrity_error_becomes_clean_404(client: AsyncClient) -> None:
    resp = await client.post("/tasks", json={"title": "x", "project_id": 424242})
    assert resp.status_code == 404
    assert resp.json()["code"] == "project_not_found"


# --- middleware request-id ----------------------------------
async def test_request_id_generated_and_respected(client: AsyncClient) -> None:
    assert (await client.get("/tasks")).headers.get("x-request-id")
    r = await client.get("/tasks", headers={"X-Request-ID": "given-42"})
    assert r.headers["x-request-id"] == "given-42"


# --- JsonFormatter ------------------------------------------
def _rec(msg: str, **extra: object) -> logging.LogRecord:
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_json_formatter_valid_and_correlated() -> None:
    token = request_id_var.set("rid-1")
    try:
        data = json.loads(JsonFormatter().format(_rec("hi", http_status=204)))
    finally:
        request_id_var.reset(token)
    assert data["msg"] == "hi"
    assert data["http_status"] == 204
    assert data["request_id"] == "rid-1"
