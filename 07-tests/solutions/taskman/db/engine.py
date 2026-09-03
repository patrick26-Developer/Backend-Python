"""Création du moteur async et de la fabrique de sessions.

Appelé une seule fois, au démarrage (`lifespan` dans `taskman/main.py`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_memory_sqlite(url: str) -> bool:
    return _is_sqlite(url) and (":memory:" in url or url.rstrip("/") == "sqlite+aiosqlite:")


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}

    if _is_memory_sqlite(database_url):
        # SQLite en mémoire : une seule connexion partagée, sinon chaque connexion
        # voit une base vide (utilisé par les tests).
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(database_url, **kwargs)

    if _is_sqlite(database_url):
        # SQLite n'applique PAS les clés étrangères par défaut : on l'active.
        @event.listens_for(engine.sync_engine, "connect")
        def _fk_pragma(dbapi_conn: DBAPIConnection, _rec: ConnectionPoolEntry) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        expire_on_commit=False,  # les objets restent utilisables après commit
        autoflush=False,  # on contrôle les flush explicitement
    )
