"""Fabriques de données de test — le *builder pattern*.

Plutôt que de répéter `{"title": "...", "project_id": ..., ...}` dans 40 tests, on
centralise la construction ici, avec des **valeurs par défaut valides** et des
surcharges ponctuelles.

    payload = task_payload(priority=5, tags=["urgent"])          # dict pour l'API
    task = make_task_create(project_id=3)                        # schéma Pydantic

Avantage : si un champ devient obligatoire, on corrige **un** endroit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from taskman.schemas import TaskCreate, UserRead, UserRole

_seq = 0


def _next() -> int:
    global _seq
    _seq += 1
    return _seq


def task_payload(**over: Any) -> dict[str, Any]:
    """Corps JSON valide pour `POST /tasks`."""
    n = _next()
    base: dict[str, Any] = {"title": f"Tâche {n}", "project_id": 1}
    return base | over


def make_task_create(**over: Any) -> TaskCreate:
    return TaskCreate(**task_payload(**over))


def future(days: int = 3) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def make_user_read(*, uid: int | None = None, role: UserRole = UserRole.member) -> UserRead:
    n = uid if uid is not None else _next()
    return UserRead(
        id=n, email=f"user{n}@test.co", role=role, is_active=True, created_at=datetime.now(UTC)
    )
