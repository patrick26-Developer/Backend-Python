"""Tests unitaires : hiérarchie d'exceptions + formatage JSON des logs."""

from __future__ import annotations

import json
import logging

from taskman.core.context import request_id_var
from taskman.core.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    TaskNotFoundError,
)
from taskman.core.logging import JsonFormatter


def test_exception_hierarchy_and_metadata() -> None:
    exc = TaskNotFoundError(42)
    assert isinstance(exc, NotFoundError)
    assert isinstance(exc, DomainError)
    assert exc.status_code == 404
    assert exc.code == "task_not_found"
    assert exc.task_id == 42
    assert "42" in exc.detail


def test_conflict_error_defaults() -> None:
    exc = ConflictError("doublon")
    assert exc.status_code == 409
    assert exc.code == "conflict"


def _record(msg: str, **extra: object) -> logging.LogRecord:
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_json_formatter_shape() -> None:
    line = JsonFormatter().format(_record("hello", http_status=200))
    data = json.loads(line)
    assert data["msg"] == "hello"
    assert data["level"] == "INFO"
    assert data["http_status"] == 200
    assert "ts" in data


def test_json_formatter_includes_request_id() -> None:
    token = request_id_var.set("rid-xyz")
    try:
        data = json.loads(JsonFormatter().format(_record("x")))
        assert data["request_id"] == "rid-xyz"
    finally:
        request_id_var.reset(token)


def test_json_formatter_no_request_id_when_unset() -> None:
    data = json.loads(JsonFormatter().format(_record("x")))
    assert "request_id" not in data
