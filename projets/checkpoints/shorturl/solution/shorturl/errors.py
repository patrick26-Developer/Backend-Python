"""Erreurs métier — découplées de HTTP (traduites en codes dans `api.py`)."""

from __future__ import annotations


class ShortUrlError(Exception):
    """Base."""


class AliasTakenError(ShortUrlError):
    """L'alias personnalisé est déjà pris (→ 409)."""


class LinkNotFoundError(ShortUrlError):
    """Aucun lien pour cet alias (→ 404)."""


class LinkExpiredError(ShortUrlError):
    """Le lien a expiré (→ 410)."""


class AliasGenerationError(ShortUrlError):
    """Impossible de générer un alias unique après N tentatives (→ 503)."""
