"""Route racine. Les sondes d'exploitation (`/health`, `/ready`, `/metrics`) sont
dans `taskman/api/routes/ops.py` (Module 09)."""

from __future__ import annotations

from fastapi import APIRouter

from taskman import __version__
from taskman.api.deps import SettingsDep

router = APIRouter(tags=["meta"])


@router.get("/")
def root(settings: SettingsDep) -> dict[str, str]:
    return {"name": settings.name, "version": __version__, "env": settings.env, "docs": "/docs"}
