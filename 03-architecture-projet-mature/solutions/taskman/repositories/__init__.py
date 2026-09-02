"""Couche persistance : le contrat (`TaskRepository`) et ses implémentations."""

from taskman.repositories.base import TaskRepository
from taskman.repositories.memory import InMemoryTaskRepository

__all__ = ["InMemoryTaskRepository", "TaskRepository"]
