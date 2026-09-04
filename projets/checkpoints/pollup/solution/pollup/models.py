"""Entités du domaine (dataclasses, pas d'ORM ici : le checkpoint porte sur les tests)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Option:
    id: int
    label: str


@dataclass
class Poll:
    id: int
    question: str
    owner: str
    options: list[Option]
    closes_at: datetime | None
    hide_results_until_closed: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # votant -> id d'option (garantit « un vote par votant »)
    votes: dict[str, int] = field(default_factory=dict)

    @property
    def is_closed(self) -> bool:
        return self.closes_at is not None and self.closes_at <= datetime.now(UTC)

    @property
    def total_votes(self) -> int:
        return len(self.votes)

    def option_ids(self) -> set[int]:
        return {o.id for o in self.options}

    def counts(self) -> dict[int, int]:
        tally = {o.id: 0 for o in self.options}
        for option_id in self.votes.values():
            tally[option_id] += 1
        return tally
