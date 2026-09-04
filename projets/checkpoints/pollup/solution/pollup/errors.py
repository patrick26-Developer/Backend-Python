"""Erreurs métier — découplées de HTTP."""

from __future__ import annotations


class PollError(Exception):
    """Base."""


class PollNotFoundError(PollError):
    """→ 404."""


class OptionNotFoundError(PollError):
    """L'option n'appartient pas à ce sondage → 422."""


class PollClosedError(PollError):
    """Le sondage est fermé → 409."""


class AlreadyVotedError(PollError):
    """Ce votant a déjà voté sur ce sondage → 409."""


class NotPollOwnerError(PollError):
    """Seul le créateur peut supprimer → 403."""


class ResultsHiddenError(PollError):
    """Résultats masqués tant que le sondage n'est pas fermé → 409."""
