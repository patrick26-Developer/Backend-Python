"""Point d'entrée : fabrique de l'application FastAPI.

`create_app()` assemble l'app à partir de la config, monte les routers, et déclare
le cycle de vie (`lifespan`). On expose aussi `app` au niveau module pour
`fastapi dev taskman/main.py`.

Lancer :  fastapi dev taskman/main.py
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taskman import __version__
from taskman.api.routes import meta, tasks
from taskman.core.config import Settings, get_settings
from taskman.repositories import InMemoryTaskRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ouverture / fermeture des ressources partagées.

    Module 03 : un simple repository en mémoire dans `app.state`.
    Module 04 : ici on ouvrira le moteur de base de données et le pool de connexions.
    """
    app.state.task_repository = InMemoryTaskRepository()
    yield
    # teardown éventuel (fermeture de pool, flush de logs…) — rien pour l'instant


def create_app(settings: Settings | None = None) -> FastAPI:
    # Si un `settings` explicite est fourni (tests, scénarios), on l'utilise PARTOUT :
    # pour construire l'app ET pour la dépendance `get_settings` des routes.
    override = settings is not None
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.name,
        version=__version__,
        summary="API de gestion de tâches — projet fil rouge du cursus Backend-Python",
        lifespan=lifespan,
        docs_url=settings.docs_url,  # None en production
        redoc_url=None if settings.is_production else "/redoc",
    )

    if override:
        app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(meta.router)
    app.include_router(tasks.router)
    return app


app = create_app()
