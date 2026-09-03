"""Schémas Pydantic — les contrats d'entrée / sortie de l'API."""

from taskman.schemas.project import ProjectCreate, ProjectPage, ProjectRead
from taskman.schemas.task import (
    ChecklistItem,
    SortKey,
    TaskBase,
    TaskCreate,
    TaskFilters,
    TaskPage,
    TaskRead,
    TaskStats,
    TaskStatus,
    TaskUpdate,
)
from taskman.schemas.user import (
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserRead,
    UserRole,
)

__all__ = [
    "ChecklistItem",
    "ProjectCreate",
    "ProjectPage",
    "ProjectRead",
    "RefreshRequest",
    "SortKey",
    "TaskBase",
    "TaskCreate",
    "TaskFilters",
    "TaskPage",
    "TaskRead",
    "TaskStats",
    "TaskStatus",
    "TaskUpdate",
    "TokenPair",
    "UserCreate",
    "UserRead",
    "UserRole",
]
