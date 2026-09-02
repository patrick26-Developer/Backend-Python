"""Fixtures partagées de la suite de tests taskman.

La suite grandit avec le cursus. Module 01 : un client HTTP synchrone et un
store remis à zéro avant chaque test. Le passage à `httpx.AsyncClient` et à une
base de test isolée est traité au Module 07.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from taskman.main import app, store


@pytest.fixture(autouse=True)
def _reset_store() -> Iterator[None]:
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
