"""Repository : `Protocol` + implémentation en mémoire.

Le service dépend du `Protocol`, jamais de l'implémentation → il se teste sans base réelle.
Brancher PostgreSQL = ajouter une classe `SqlAlchemyPollRepository` (patron du Module 04),
rien à changer dans le service.
"""

from __future__ import annotations

import itertools
from datetime import datetime
from typing import Protocol

from pollup.models import Option, Poll


class PollRepository(Protocol):
    def create(
        self,
        *,
        question: str,
        options: list[str],
        owner: str,
        closes_at: datetime | None,
        hide_results_until_closed: bool,
    ) -> Poll: ...

    def get(self, poll_id: int) -> Poll | None: ...

    def delete(self, poll_id: int) -> None: ...

    def record_vote(self, poll_id: int, *, voter: str, option_id: int) -> None: ...


class InMemoryPollRepository:
    def __init__(self) -> None:
        self._polls: dict[int, Poll] = {}
        self._poll_ids = itertools.count(1)
        self._option_ids = itertools.count(1)

    def create(
        self,
        *,
        question: str,
        options: list[str],
        owner: str,
        closes_at: datetime | None,
        hide_results_until_closed: bool,
    ) -> Poll:
        poll = Poll(
            id=next(self._poll_ids),
            question=question,
            owner=owner,
            options=[Option(id=next(self._option_ids), label=label) for label in options],
            closes_at=closes_at,
            hide_results_until_closed=hide_results_until_closed,
        )
        self._polls[poll.id] = poll
        return poll

    def get(self, poll_id: int) -> Poll | None:
        return self._polls.get(poll_id)

    def delete(self, poll_id: int) -> None:
        self._polls.pop(poll_id, None)

    def record_vote(self, poll_id: int, *, voter: str, option_id: int) -> None:
        self._polls[poll_id].votes[voter] = option_id
