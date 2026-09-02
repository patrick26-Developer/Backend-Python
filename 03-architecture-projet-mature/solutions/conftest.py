"""Fixtures pour tester la solution du Module 03 (standalone).

`cd 03-architecture-projet-mature/solutions && pytest`
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from taskman.api.deps import get_task_repository
from taskman.core.config import Settings
from taskman.main import create_app
from taskman.repositories import InMemoryTaskRepository


@pytest.fixture
def repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


@pytest.fixture
def client(repository: InMemoryTaskRepository) -> Iterator[TestClient]:
    app = create_app(Settings(env="test"))
    app.dependency_overrides[get_task_repository] = lambda: repository
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
