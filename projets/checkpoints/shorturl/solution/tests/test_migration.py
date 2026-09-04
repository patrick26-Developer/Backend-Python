"""Vérifie que `alembic upgrade head` construit bien le schéma (DoD n°1)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _env(db: Path) -> dict[str, str]:
    # on hérite de l'environnement complet (sur Windows, python.exe a besoin de SYSTEMROOT…)
    return {**os.environ, "SHORTURL_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}


def _alembic(db: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=_env(db),
        capture_output=True,
        text=True,
    )


@pytest.mark.slow
def test_alembic_upgrade_head_creates_schema(tmp_path: Path) -> None:
    db = tmp_path / "mig.db"
    run = _alembic(db, "upgrade", "head")
    assert run.returncode == 0, run.stderr
    assert db.exists()

    con = sqlite3.connect(db)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    finally:
        con.close()
    assert "links" in tables
    assert "ix_links_alias" in indexes


@pytest.mark.slow
def test_alembic_check_no_pending_changes(tmp_path: Path) -> None:
    """Le modèle ORM et les migrations sont synchronisés (`alembic check`)."""
    db = tmp_path / "chk.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    run = _alembic(db, "check")
    assert run.returncode == 0, run.stdout + run.stderr
