from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pollup.api import create_app
from pollup.repository import InMemoryPollRepository
from pollup.service import PollService


@pytest.fixture
def repo() -> InMemoryPollRepository:
    return InMemoryPollRepository()


@pytest.fixture
def service(repo: InMemoryPollRepository) -> PollService:
    return PollService(repo)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c
