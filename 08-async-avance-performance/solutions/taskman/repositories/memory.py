"""Implémentations **en mémoire** des repositories.

Rôle depuis le Module 04 : support des tests de la couche **service** (rapides,
sans base). Async pour respecter les `Protocol`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from operator import attrgetter

from taskman.db.models import RefreshTokenRow, UserRow
from taskman.schemas import (
    ProjectCreate,
    ProjectRead,
    SortKey,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    UserRole,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _sorted(rows: list[TaskRead], sort: SortKey) -> list[TaskRead]:
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    rows.sort(key=attrgetter("created_at"))
    if field == "due_date":
        rows.sort(
            key=lambda t: (t.due_date is None, t.due_date or datetime.min.replace(tzinfo=UTC)),
            reverse=reverse,
        )
    else:
        rows.sort(key=attrgetter(field), reverse=reverse)
    return rows


class NullUnitOfWork:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._items: dict[int, TaskRead] = {}
        self._owner: dict[int, int] = {}
        self._seq = 0

    def clear(self) -> None:
        self._items.clear()
        self._owner.clear()
        self._seq = 0

    async def create(self, data: TaskCreate, *, owner_id: int) -> TaskRead:
        self._seq += 1
        now = _now()
        task = TaskRead(
            id=self._seq,
            status=TaskStatus.todo,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._items[task.id] = task
        self._owner[task.id] = owner_id
        return task

    async def get(self, task_id: int) -> TaskRead | None:
        return self._items.get(task_id)

    async def get_owner_id(self, task_id: int) -> int | None:
        return self._owner.get(task_id)

    async def list_page(
        self, filters: TaskFilters, *, owner_id: int | None
    ) -> tuple[list[TaskRead], int]:
        rows = [
            t for t in self._items.values() if owner_id is None or self._owner.get(t.id) == owner_id
        ]
        if filters.status is not None:
            rows = [t for t in rows if t.status == filters.status]
        if filters.min_priority is not None:
            rows = [t for t in rows if t.priority >= filters.min_priority]
        if filters.project_id is not None:
            rows = [t for t in rows if t.project_id == filters.project_id]
        if filters.q:
            needle = filters.q.casefold()
            rows = [
                t
                for t in rows
                if needle in t.title.casefold()
                or (t.description is not None and needle in t.description.casefold())
            ]
        total = len(rows)
        rows = _sorted(rows, filters.sort)
        return rows[filters.offset : filters.offset + filters.limit], total

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        current = self._items.get(task_id)
        if current is None:
            return None
        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current
        data = current.model_dump()
        data.update(patch)
        data["updated_at"] = _now()
        updated = TaskRead.model_validate(data)
        self._items[task_id] = updated
        return updated

    async def list_keyset(
        self, *, owner_id: int | None, limit: int, after: tuple[datetime, int] | None
    ) -> list[TaskRead]:
        rows = [
            t for t in self._items.values() if owner_id is None or self._owner.get(t.id) == owner_id
        ]
        rows.sort(key=lambda t: (t.created_at, t.id), reverse=True)
        if after is not None:
            rows = [t for t in rows if (t.created_at, t.id) < after]
        return rows[:limit]

    async def iter_by_owner(self, owner_id: int | None) -> AsyncIterator[TaskRead]:
        for t in sorted(self._items.values(), key=attrgetter("id")):
            if owner_id is None or self._owner.get(t.id) == owner_id:
                yield t

    async def project_stats(self, project_id: int) -> tuple[dict[str, int], int]:
        rows = [t for t in self._items.values() if t.project_id == project_id]
        by_status: dict[str, int] = {}
        for t in rows:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        overdue = sum(1 for t in rows if t.is_overdue)
        return by_status, overdue

    async def mark_completed(self, task_id: int) -> TaskRead | None:
        current = self._items.get(task_id)
        if current is None:
            return None
        updated = current.model_copy(
            update={
                "status": TaskStatus.done,
                "completed_at": _now(),
                "updated_at": _now(),
            }
        )
        self._items[task_id] = updated
        return updated

    async def delete(self, task_id: int) -> bool:
        self._owner.pop(task_id, None)
        return self._items.pop(task_id, None) is not None


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._items: dict[int, ProjectRead] = {}
        self._owner: dict[int, int] = {}
        self._seq = 0

    def clear(self) -> None:
        self._items.clear()
        self._owner.clear()
        self._seq = 0

    async def create(self, data: ProjectCreate, *, owner_id: int) -> ProjectRead:
        self._seq += 1
        project = ProjectRead(id=self._seq, name=data.name, created_at=_now(), task_count=0)
        self._items[project.id] = project
        self._owner[project.id] = owner_id
        return project

    async def get(self, project_id: int) -> ProjectRead | None:
        return self._items.get(project_id)

    async def get_owner_id(self, project_id: int) -> int | None:
        return self._owner.get(project_id)

    async def list_page(
        self, *, owner_id: int | None, limit: int, offset: int
    ) -> tuple[list[ProjectRead], int]:
        rows = sorted(
            (
                p
                for p in self._items.values()
                if owner_id is None or self._owner.get(p.id) == owner_id
            ),
            key=attrgetter("id"),
        )
        return rows[offset : offset + limit], len(rows)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, UserRow] = {}
        self._seq = 0

    def clear(self) -> None:
        self._by_id.clear()
        self._seq = 0

    async def create(self, *, email: str, hashed_password: str) -> UserRow:
        from taskman.core.exceptions import EmailAlreadyRegisteredError

        if any(u.email == email for u in self._by_id.values()):
            raise EmailAlreadyRegisteredError(email)
        self._seq += 1
        row = UserRow(
            id=self._seq,
            email=email,
            hashed_password=hashed_password,
            role=UserRole.member,
            is_active=True,
            created_at=_now(),
        )
        self._by_id[row.id] = row
        return row

    async def get(self, user_id: int) -> UserRow | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> UserRow | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def list_page(self, *, limit: int, offset: int) -> tuple[list[UserRow], int]:
        rows = sorted(self._by_id.values(), key=attrgetter("id"))
        return rows[offset : offset + limit], len(rows)


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self._by_jti: dict[str, RefreshTokenRow] = {}

    def clear(self) -> None:
        self._by_jti.clear()

    async def add(self, *, jti: str, user_id: int, expires_at: datetime) -> None:
        self._by_jti[jti] = RefreshTokenRow(
            jti=jti, user_id=user_id, expires_at=expires_at, revoked=False, created_at=_now()
        )

    async def get(self, jti: str) -> RefreshTokenRow | None:
        return self._by_jti.get(jti)

    async def revoke(self, jti: str) -> None:
        row = self._by_jti.get(jti)
        if row is not None:
            row.revoked = True
