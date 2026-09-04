"""Règles métier — testées SANS HTTP, une règle = un test (ordre TDD).

Chaque test correspond à une ligne de la Definition of Done du brief.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pollup.errors import (
    AlreadyVotedError,
    NotPollOwnerError,
    OptionNotFoundError,
    PollClosedError,
    PollNotFoundError,
    ResultsHiddenError,
)
from pollup.models import Poll
from pollup.service import PollService


def _poll(service: PollService, *, hide: bool = False, closes_at: datetime | None = None) -> Poll:
    return service.create_poll(
        question="Café ou thé ?",
        options=["café", "thé"],
        owner="alice",
        closes_at=closes_at,
        hide_results_until_closed=hide,
    )


def test_create_assigns_ids_to_poll_and_options(service: PollService) -> None:
    poll = _poll(service)
    assert poll.id == 1
    assert [o.id for o in poll.options] == [1, 2]
    assert poll.total_votes == 0


def test_get_unknown_poll_raises(service: PollService) -> None:
    with pytest.raises(PollNotFoundError):
        service.get_poll(999)


def test_vote_counts_once_per_voter(service: PollService) -> None:
    poll = _poll(service)
    service.vote(poll.id, voter="bob", option_id=poll.options[0].id)
    assert service.get_poll(poll.id).total_votes == 1


def test_second_vote_by_same_voter_is_rejected(service: PollService) -> None:
    poll = _poll(service)
    service.vote(poll.id, voter="bob", option_id=poll.options[0].id)
    with pytest.raises(AlreadyVotedError):
        service.vote(poll.id, voter="bob", option_id=poll.options[1].id)


def test_vote_on_closed_poll_is_rejected(service: PollService) -> None:
    poll = _poll(service, closes_at=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(PollClosedError):
        service.vote(poll.id, voter="bob", option_id=poll.options[0].id)


def test_vote_with_option_from_another_poll_is_rejected(service: PollService) -> None:
    poll_a = _poll(service)
    poll_b = _poll(service)
    foreign_option = poll_b.options[0].id
    with pytest.raises(OptionNotFoundError):
        service.vote(poll_a.id, voter="bob", option_id=foreign_option)


def test_results_percentages(service: PollService) -> None:
    poll = _poll(service)
    service.vote(poll.id, voter="a", option_id=poll.options[0].id)
    service.vote(poll.id, voter="b", option_id=poll.options[0].id)
    service.vote(poll.id, voter="c", option_id=poll.options[1].id)

    results = service.results(poll.id)
    assert results.total_votes == 3
    by_id = {r.option_id: r for r in results.results}
    assert by_id[poll.options[0].id].count == 2
    assert by_id[poll.options[0].id].percent == 66.7
    assert by_id[poll.options[1].id].percent == 33.3


def test_results_with_zero_votes_are_all_zero_percent(service: PollService) -> None:
    poll = _poll(service)
    results = service.results(poll.id)
    assert all(r.percent == 0.0 and r.count == 0 for r in results.results)


def test_hidden_results_blocked_for_stranger_until_closed(service: PollService) -> None:
    poll = _poll(service, hide=True)
    with pytest.raises(ResultsHiddenError):
        service.results(poll.id, requester="stranger")


def test_hidden_results_visible_to_owner(service: PollService) -> None:
    poll = _poll(service, hide=True)
    assert service.results(poll.id, requester="alice").total_votes == 0


def test_hidden_results_visible_to_all_once_closed(service: PollService) -> None:
    poll = _poll(service, hide=True, closes_at=datetime.now(UTC) - timedelta(seconds=1))
    assert service.results(poll.id, requester="stranger").total_votes == 0


def test_only_owner_can_delete(service: PollService) -> None:
    poll = _poll(service)
    with pytest.raises(NotPollOwnerError):
        service.delete_poll(poll.id, requester="mallory")
    service.delete_poll(poll.id, requester="alice")
    with pytest.raises(PollNotFoundError):
        service.get_poll(poll.id)
