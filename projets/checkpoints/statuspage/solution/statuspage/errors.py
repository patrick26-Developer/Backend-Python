"""Erreurs métier — découplées de HTTP."""

from __future__ import annotations


class StatusPageError(Exception):
    """Base."""


class ServiceNotFoundError(StatusPageError):
    """→ 404."""


class ServiceNameTakenError(StatusPageError):
    """→ 409."""


class IncidentNotFoundError(StatusPageError):
    """→ 404."""


class InvalidTransitionError(StatusPageError):
    """Transition d'incident illégale → 409."""
