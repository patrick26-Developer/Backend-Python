"""Point d'entrée : fabrique de l'application FastAPI.

Lancer :  fastapi dev taskman/main.py
Migrations :  alembic upgrade head
Worker (si APP_REDIS_URL) :  taskiq worker taskman.worker:broker
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from taskman import __version__
from taskman.api.errors import register_error_handlers
from taskman.api.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from taskman.api.ratelimit import build_rate_limiter
from taskman.api.routes import admin, auth, meta, ops, projects, tasks
from taskman.core.cache import build_cache
from taskman.core.config import Settings, get_settings
from taskman.core.logging import configure_logging
from taskman.db.engine import create_engine, create_session_factory
from taskman.observability import tracing
from taskman.observability.metrics import MetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    engine = create_engine(settings.database_url, echo=settings.db_echo)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.cache = build_cache(settings.redis_url)
    app.state.rate_limiter = build_rate_limiter(settings.redis_url)

    tracing.instrument_engine(engine.sync_engine)  # spans SQL si le tracing est actif

    from taskman.tasks import broker

    if not broker.is_worker_process:
        await broker.startup()

    try:
        yield
    finally:
        if not broker.is_worker_process:
            await broker.shutdown()
        await app.state.cache.close()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    override = settings is not None
    settings = settings or get_settings()

    configure_logging(level=settings.log_level, json_output=settings.use_json_logs)
    tracing.configure_tracing(
        enabled=settings.otel_enabled,
        endpoint=settings.otel_endpoint,
        service_name=settings.name,
    )

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

    # Ordre : le dernier ajouté est le plus EXTERNE (voit la requête en premier).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,  # jamais "*" avec allow_credentials
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            max_age=600,
        )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    tracing.instrument_app(app)

    app.include_router(meta.router)
    app.include_router(ops.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    return app


app = create_app()
