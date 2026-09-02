"""Couche persistance : contrats (`Protocol`) et implémentations."""

from taskman.repositories.base import (
    ProjectRepository,
    TaskRepository,
    UnitOfWork,
)
from taskman.repositories.memory import (
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    NullUnitOfWork,
)
from taskman.repositories.sqlalchemy import (
    SqlAlchemyProjectRepository,
    SqlAlchemyTaskRepository,
)

__all__ = [
    "InMemoryProjectRepository",
    "InMemoryTaskRepository",
    "NullUnitOfWork",
    "ProjectRepository",
    "SqlAlchemyProjectRepository",
    "SqlAlchemyTaskRepository",
    "TaskRepository",
    "UnitOfWork",
]
