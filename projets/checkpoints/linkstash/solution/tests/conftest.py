from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from linkstash.api import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def sample() -> dict[str, object]:
    return {
        "url": "https://fastapi.tiangolo.com/tutorial/",
        "title": "FastAPI — Tutorial",
        "note": "Le point de départ officiel.",
        "tags": ["Python", "fastapi", "  Python "],  # doublon + casse : normalisés
        "favorite": True,
    }
