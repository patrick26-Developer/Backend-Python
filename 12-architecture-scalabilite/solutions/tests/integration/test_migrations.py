"""Vérifie que les migrations Alembic sont **à jour** avec les modèles ORM.

Si tu modifies `taskman/db/models.py` sans générer la migration correspondante,
ce test échoue. C'est le garde-fou contre le « ça marche en local, ça casse en prod ».
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_no_pending_migration(tmp_path: Path) -> None:
    db = tmp_path / "check.db"
    env = {"APP_DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**_base_env(), **env},
    )
    assert up.returncode == 0, up.stderr

    check = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**_base_env(), **env},
    )
    assert check.returncode == 0, (
        "Des changements de modèle ne sont pas migrés. "
        "Lance : alembic revision --autogenerate -m '...'\n" + check.stdout + check.stderr
    )


def _base_env() -> dict[str, str]:
    import os

    return dict(os.environ)
