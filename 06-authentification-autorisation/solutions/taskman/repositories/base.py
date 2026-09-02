"""Contrats des couches persistance et transaction.

Async depuis le Module 04. Module 06 : les repositories deviennent **conscients du
propriétaire** (`owner_id`) — l'isolation des données passe par la persistance, pas
seulement par un `if` dans le service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from taskman.db.models import RefreshTokenRow, UserRow
from taskman.schemas import (
    ProjectCreate,
    ProjectRead,
    TaskCreate,
    TaskFilters,
    TaskRead,
    TaskUpdate,
)


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class TaskRepository(Protocol):
    async def create(self, data: TaskCreate, *, owner_id: int) -> TaskRead: ...

    async def get(self, task_id: int) -> TaskRead | None: ...

    async def get_owner_id(self, task_id: int) -> int | None: ...

    async def list(
        self, filters: TaskFilters, *, owner_id: int | None
    ) -> tuple[list[TaskRead], int]: ...

    async def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None: ...

    async def delete(self, task_id: int) -> bool: ...


class ProjectRepository(Protocol):
    async def create(self, data: ProjectCreate, *, owner_id: int) -> ProjectRead: ...

    async def get(self, project_id: int) -> ProjectRead | None: ...

    async def get_owner_id(self, project_id: int) -> int | None: ...

    async def list(
        self, *, owner_id: int | None, limit: int, offset: int
    ) -> tuple[list[ProjectRead], int]: ...


class UserRepository(Protocol):
    async def create(self, *, email: str, hashed_password: str) -> UserRow: ...

    async def get(self, user_id: int) -> UserRow | None: ...

    async def get_by_email(self, email: str) -> UserRow | None: ...

    async def list(self, *, limit: int, offset: int) -> tuple[list[UserRow], int]: ...


class RefreshTokenRepository(Protocol):
    async def add(self, *, jti: str, user_id: int, expires_at: datetime) -> None: ...

    async def get(self, jti: str) -> RefreshTokenRow | None: ...

    async def revoke(self, jti: str) -> None: ...
