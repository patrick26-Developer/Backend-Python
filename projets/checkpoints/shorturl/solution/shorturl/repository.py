"""Repository : le SEUL endroit qui parle SQL. Renvoie des `LinkRow` ou `None`.

`create` laisse remonter l'`IntegrityError` (violation d'unicité de l'alias) : c'est au
service de décider quoi en faire (réessayer avec un autre alias, ou renvoyer 409).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shorturl.models import LinkRow


class LinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, alias: str, target_url: str, expires_at: datetime | None) -> LinkRow:
        row = LinkRow(alias=alias, target_url=target_url, expires_at=expires_at)
        self._session.add(row)
        try:
            await self._session.flush()  # déclenche l'INSERT → l'unicité est vérifiée ICI
        except IntegrityError:
            await self._session.rollback()
            raise
        return row

    async def get_by_alias(self, alias: str) -> LinkRow | None:
        result = await self._session.scalars(select(LinkRow).where(LinkRow.alias == alias))
        return result.one_or_none()

    async def delete_by_alias(self, alias: str) -> bool:
        row = await self.get_by_alias(alias)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def register_click(self, alias: str) -> None:
        """Incrément atomique — un seul UPDATE, indépendant de la lecture de redirection."""
        await self._session.execute(
            update(LinkRow)
            .where(LinkRow.alias == alias)
            .values(clicks=LinkRow.clicks + 1, last_clicked_at=datetime.now(UTC))
        )
