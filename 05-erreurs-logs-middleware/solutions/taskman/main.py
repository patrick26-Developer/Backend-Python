"""Point d'entrée : fabrique de l'application FastAPI.

Lancer :  fastapi dev taskman/main.py
Avant la 1re requête sur une base neuve :  alembic upgrade head
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taskman import __version__
from taskman.api.errors import register_error_handlers
from taskman.api.middleware import RequestContextMiddleware
from taskman.api.routes import meta, projects, tasks
from taskman.core.config import Settings, get_settings
from taskman.core.logging import configure_logging
from taskman.db.engine import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings.database_url, echo=settings.db_echo)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    override = settings is not None
    settings = settings or get_settings()

    configure_logging(level=settings.log_level, json_output=settings.use_json_logs)

    app = FastAPI(
        title=settings.name,
        version=__version__,
        summary="API de gestion de tâches — projet fil rouge du cursus Backend-Python",
        lifespan=lifespan,
        docs_url=settings.docs_url,
        redoc_url=None if settings.is_production else "/redoc",
    )
    app.state.settings = settings
    if override:
        app.dependency_overrides[get_settings] = lambda: settings

    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(meta.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    return app


app = create_app()
