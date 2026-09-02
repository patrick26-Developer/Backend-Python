"""Socle SQLAlchemy : la classe `Base` et un type date-heure fiable.

`TZDateTime` garantit que les `datetime` ressortent **timezone-aware** (UTC).
SQLite, en particulier, perd le fuseau — ce type le rétablit, côté écriture ET
lecture. Sur PostgreSQL c'est déjà correct, mais le type reste inoffensif.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Dialect, types
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base commune à tous les modèles ORM."""


class TZDateTime(types.TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def utcnow() -> datetime:
    """Défaut de colonne : maintenant, en UTC *aware*."""
    return datetime.now(UTC)


# Métadonnées exposées pour Alembic (voir alembic/env.py).
metadata: Any = Base.metadata
