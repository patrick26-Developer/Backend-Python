"""Couche métier : règles, génération d'alias, gestion de l'expiration.

Ne connaît ni FastAPI ni `Request`/`Response` — seulement le repository et les erreurs
du domaine.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from shorturl.config import Settings
from shorturl.errors import (
    AliasGenerationError,
    AliasTakenError,
    LinkExpiredError,
    LinkNotFoundError,
)
from shorturl.models import LinkRow
from shorturl.repository import LinkRepository

_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _random_alias(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class LinkService:
    def __init__(self, repo: LinkRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def create(
        self, *, target_url: str, custom_alias: str | None, expires_at: datetime | None
    ) -> LinkRow:
        if custom_alias is not None:
            try:
                return await self._repo.create(
                    alias=custom_alias, target_url=target_url, expires_at=expires_at
                )
            except IntegrityError as exc:
                raise AliasTakenError(custom_alias) from exc

        # alias auto : on tente quelques aliases aléatoires ; la contrainte d'unicité de la
        # base tranche les collisions (y compris entre deux requêtes concurrentes).
        for _ in range(self._settings.alias_max_attempts):
            alias = _random_alias(self._settings.alias_length)
            try:
                return await self._repo.create(
                    alias=alias, target_url=target_url, expires_at=expires_at
                )
            except IntegrityError:
                continue
        raise AliasGenerationError

    async def resolve(self, alias: str) -> str:
        """Renvoie l'URL cible ou lève. N'incrémente PAS les clics (fait à part, non bloquant)."""
        row = await self._repo.get_by_alias(alias)
        if row is None:
            raise LinkNotFoundError(alias)
        if row.expires_at is not None and row.expires_at <= datetime.now(UTC):
            raise LinkExpiredError(alias)
        return row.target_url

    async def stats(self, alias: str) -> LinkRow:
        row = await self._repo.get_by_alias(alias)
        if row is None:
            raise LinkNotFoundError(alias)
        return row

    async def delete(self, alias: str) -> None:
        if not await self._repo.delete_by_alias(alias):
            raise LinkNotFoundError(alias)

    def short_url(self, alias: str) -> str:
        return f"{self._settings.base_url.rstrip('/')}/{alias}"
