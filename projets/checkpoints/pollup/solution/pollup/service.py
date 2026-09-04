"""Couche métier. Testée directement (sans HTTP) dans `tests/test_service.py`."""

from __future__ import annotations

from datetime import datetime

from pollup.errors import (
    AlreadyVotedError,
    NotPollOwnerError,
    OptionNotFoundError,
    PollClosedError,
    PollNotFoundError,
    ResultsHiddenError,
)
from pollup.models import Poll
from pollup.repository import PollRepository
from pollup.schemas import OptionResult, PollResults


class PollService:
    def __init__(self, repo: PollRepository) -> None:
        self._repo = repo

    def create_poll(
        self,
        *,
        question: str,
        options: list[str],
        owner: str,
        closes_at: datetime | None,
        hide_results_until_closed: bool,
    ) -> Poll:
        return self._repo.create(
            question=question,
            options=options,
            owner=owner,
            closes_at=closes_at,
            hide_results_until_closed=hide_results_until_closed,
        )

    def get_poll(self, poll_id: int) -> Poll:
        poll = self._repo.get(poll_id)
        if poll is None:
            raise PollNotFoundError(poll_id)
        return poll

    def vote(self, poll_id: int, *, voter: str, option_id: int) -> None:
        poll = self.get_poll(poll_id)
        if poll.is_closed:
            raise PollClosedError(poll_id)
        if option_id not in poll.option_ids():
            raise OptionNotFoundError(option_id)
        if voter in poll.votes:
            raise AlreadyVotedError(voter)
        self._repo.record_vote(poll_id, voter=voter, option_id=option_id)

    def results(self, poll_id: int, *, requester: str | None = None) -> PollResults:
        poll = self.get_poll(poll_id)
        if poll.hide_results_until_closed and not poll.is_closed and requester != poll.owner:
            raise ResultsHiddenError(poll_id)
        counts = poll.counts()
        total = poll.total_votes
        by_label = {o.id: o.label for o in poll.options}
        return PollResults(
            poll_id=poll.id,
            total_votes=total,
            results=[
                OptionResult(
                    option_id=oid,
                    label=by_label[oid],
                    count=count,
                    percent=round(100 * count / total, 1) if total else 0.0,
                )
                for oid, count in counts.items()
            ],
        )

    def delete_poll(self, poll_id: int, *, requester: str) -> None:
        poll = self.get_poll(poll_id)
        if poll.owner != requester:
            raise NotPollOwnerError(requester)
        self._repo.delete(poll_id)
