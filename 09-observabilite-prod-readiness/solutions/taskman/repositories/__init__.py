"""Couche persistance : contrats (`Protocol`) et implémentations."""

from taskman.repositories.base import (
    ProjectRepository,
    RefreshTokenRepository,
    TaskRepository,
    UnitOfWork,
    UserRepository,
)
from taskman.repositories.memory import (
    InMemoryProjectRepository,
    InMemoryRefreshTokenRepository,
    InMemoryTaskRepository,
    InMemoryUserRepository,
    NullUnitOfWork,
)
from taskman.repositories.sqlalchemy import (
    SqlAlchemyProjectRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyTaskRepository,
    SqlAlchemyUserRepository,
)

__all__ = [
    "InMemoryProjectRepository",
    "InMemoryRefreshTokenRepository",
    "InMemoryTaskRepository",
    "InMemoryUserRepository",
    "NullUnitOfWork",
    "ProjectRepository",
    "RefreshTokenRepository",
    "SqlAlchemyProjectRepository",
    "SqlAlchemyRefreshTokenRepository",
    "SqlAlchemyTaskRepository",
    "SqlAlchemyUserRepository",
    "TaskRepository",
    "UnitOfWork",
    "UserRepository",
]
