"""Solution Module 01 — store en mémoire.

RAPPEL : échafaudage jetable. Remplacé par un vrai repository + SQLAlchemy au
Module 04. Pas thread-safe, pas persistant. Il sert à isoler l'apprentissage de
HTTP/FastAPI de celui des bases de données.

Le store expose une API "métier" (create/get/list/update/delete) et ne connaît
RIEN de FastAPI ni de HTTP. C'est déjà, en germe, la séparation des couches du
Module 03.
"""

from __future__ import annotations

from datetime import UTC, datetime
from operator import attrgetter

from .models import Task, TaskCreate, TaskStatus, TaskUpdate

SortKey = str  # "priority" | "-priority" | "created_at" | "-created_at"


def _now() -> datetime:
    return datetime.now(UTC)


def _sorted(rows: list[Task], sort: SortKey) -> list[Task]:
    """Tri (fonction module : évite que `list[...]` désigne la méthode `list`).

    Clé secondaire `created_at` croissant pour un ordre 100 % déterministe.
    """
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in {"priority", "created_at"}:
        field, reverse = "priority", True
    rows.sort(key=attrgetter("created_at"))
    rows.sort(key=attrgetter(field), reverse=reverse)
    return rows


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._items: dict[int, Task] = {}
        self._seq: int = 0

    def clear(self) -> None:
        """Utile pour repartir d'un état propre entre deux tests."""
        self._items.clear()
        self._seq = 0

    def create(self, data: TaskCreate) -> Task:
        self._seq += 1
        now = _now()
        task = Task(
            id=self._seq,
            status=TaskStatus.todo,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._items[task.id] = task
        return task

    def get(self, task_id: int) -> Task | None:
        return self._items.get(task_id)

    def list(
        self,
        *,
        status: TaskStatus | None = None,
        min_priority: int | None = None,
        sort: SortKey = "-priority",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        rows = list(self._items.values())

        if status is not None:
            rows = [t for t in rows if t.status == status]
        if min_priority is not None:
            rows = [t for t in rows if t.priority >= min_priority]

        total = len(rows)
        rows = _sorted(rows, sort)
        return rows[offset : offset + limit], total

    def update(self, task_id: int, changes: TaskUpdate) -> Task | None:
        current = self._items.get(task_id)
        if current is None:
            return None

        # exclude_unset : seuls les champs RÉELLEMENT fournis par le client
        # sont dans le dict. `{}` ne modifie rien ; `{"description": null}`
        # met bien la description à None.
        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current

        updated = current.model_copy(update={**patch, "updated_at": _now()})
        self._items[task_id] = updated
        return updated

    def delete(self, task_id: int) -> bool:
        return self._items.pop(task_id, None) is not None
