"""Routes de service : racine et sonde de vie."""

from __future__ import annotations

from fastapi import APIRouter

from taskman import __version__
from taskman.api.deps import SettingsDep

router = APIRouter(tags=["meta"])


@router.get("/")
def root(settings: SettingsDep) -> dict[str, str]:
    return {"name": settings.name, "version": __version__, "env": settings.env, "docs": "/docs"}


@router.get("/health")
def health() -> dict[str, str]:
    # Liveness seulement. La readiness (DB, etc.) arrive au Module 09.
    return {"status": "ok"}
