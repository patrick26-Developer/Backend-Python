"""Tests unitaires des schémas Pydantic (Module 02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from taskman.schemas import TaskCreate, TaskFilters, TaskRead, TaskStatus, TaskUpdate

FUTURE = datetime.now(UTC) + timedelta(days=3)
PAST = datetime.now(UTC) - timedelta(days=3)


def _read(**over: object) -> TaskRead:
    base: dict[str, object] = {
        "id": 1,
        "project_id": 1,
        "title": "x",
        "status": TaskStatus.todo,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    return TaskRead(**{**base, **over})  # type: ignore[arg-type]


# --- TaskCreate ---------------------------------------------------------
def test_create_requires_project_id() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="x")  # type: ignore[call-arg]


def test_create_rejects_past_due_date() -> None:
    with pytest.raises(ValidationError, match="futur"):
        TaskCreate(title="x", project_id=1, due_date=PAST)


def test_create_strips_and_lowercases_tags() -> None:
    t = TaskCreate(title="  Titre  ", project_id=1, tags=["  URGENT ", "Docs"])
    assert t.title == "Titre"
    assert t.tags == ["urgent", "docs"]


def test_create_rejects_bad_email() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="x", project_id=1, assignee_email="pas-un-email")


def test_estimate_rejects_three_decimals() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="x", project_id=1, estimate_hours=Decimal("1.005"))


def test_nested_checklist_error_path_is_precise() -> None:
    with pytest.raises(ValidationError) as exc:
        TaskCreate(title="x", project_id=1, checklist=[{"label": "   "}])  # type: ignore[list-item]
    assert exc.value.errors()[0]["loc"] == ("checklist", 0, "label")


# --- TaskUpdate --------------------------------------------------------
def test_update_title_not_nullable() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(title=None)  # explicitement null -> refusé


def test_update_due_date_null_is_allowed() -> None:
    u = TaskUpdate(due_date=None)
    assert "due_date" in u.model_fields_set
    assert u.due_date is None


def test_update_due_date_past_rejected_when_provided() -> None:
    with pytest.raises(ValidationError, match="futur"):
        TaskUpdate(due_date=PAST)


# --- TaskRead / is_overdue -------------------------------------------
def test_is_overdue_false_without_due_date() -> None:
    assert _read().is_overdue is False


def test_is_overdue_true_when_past_and_not_done() -> None:
    assert _read(due_date=PAST, status=TaskStatus.doing).is_overdue is True


def test_is_overdue_false_when_done() -> None:
    assert _read(due_date=PAST, status=TaskStatus.done).is_overdue is False


def test_is_overdue_in_dump() -> None:
    assert _read(due_date=PAST, status=TaskStatus.todo).model_dump()["is_overdue"] is True


# --- TaskFilters -----------------------------------------------------
def test_filters_reject_unknown_field() -> None:
    with pytest.raises(ValidationError):
        TaskFilters(statuss="done")  # type: ignore[call-arg]


def test_filters_defaults() -> None:
    f = TaskFilters()
    assert (f.limit, f.offset, f.sort) == (20, 0, "-priority")
