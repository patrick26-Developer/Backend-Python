"""Environnement Alembic — configuré pour un moteur **async** (SQLAlchemy 2.0).

- la chaîne de connexion vient de `taskman.core.config` (pas de `alembic.ini`) ;
- `target_metadata` = les tables déclarées dans `taskman/db/models.py` ;
- `--autogenerate` compare ces modèles à la base réelle.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

# Enregistre les modèles auprès de Base.metadata (import pour effet de bord).
import taskman.db.models  # noqa: F401
from taskman.core.config import get_settings
from taskman.db.base import Base, TZDateTime
from taskman.db.engine import create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Rend `TZDateTime` comme un simple `DateTime(timezone=True)` dans les
    migrations : la coercition UTC est un comportement d'exécution, la colonne
    stockée est identique."""
    if type_ == "type" and isinstance(obj, TZDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,  # nécessaire pour ALTER TABLE sous SQLite
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine: AsyncEngine = create_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
