"""Couche HTTP : routes, middleware de corrélation, lifespan (worker), exploitation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from statuspage import __version__
from statuspage.config import Settings, get_settings
from statuspage.db import Base, create_engine, create_session_factory, get_session
from statuspage.errors import (
    IncidentNotFoundError,
    InvalidTransitionError,
    ServiceNameTakenError,
    ServiceNotFoundError,
    StatusPageError,
)
from statuspage.models import (  # noqa: F401  (enregistre les tables)
    CheckRow,
    IncidentRow,
    ServiceRow,
)
from statuspage.monitor import Monitor
from statuspage.observability import Metrics, configure_logging, correlation_id
from statuspage.repository import CheckRepository, IncidentRepository, ServiceRepository
from statuspage.schemas import (
    CheckPage,
    IncidentCreate,
    IncidentRead,
    IncidentUpdate,
    ServiceCreate,
    ServiceRead,
    StatusSummary,
)
from statuspage.service import StatusService

logger = logging.getLogger("statuspage.api")

_ERROR_STATUS: dict[type[StatusPageError], int] = {
    ServiceNotFoundError: status.HTTP_404_NOT_FOUND,
    IncidentNotFoundError: status.HTTP_404_NOT_FOUND,
    ServiceNameTakenError: status.HTTP_409_CONFLICT,
    InvalidTransitionError: status.HTTP_409_CONFLICT,
}


class CorrelationMiddleware:
    """Middleware ASGI **pur** (pas `BaseHTTPMiddleware` : celui-ci exécute la suite dans une
    autre tâche, la `ContextVar` posée n'atteindrait pas les handlers).

    Chaque requête reçoit un `request-id` (repris de l'en-tête `x-request-id` s'il existe),
    propagé aux logs via la `ContextVar` et renvoyé dans la réponse.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        rid = headers.get(b"x-request-id", b"").decode() or f"req-{uuid.uuid4().hex[:12]}"
        token = correlation_id.set(rid)

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", rid.encode()),
                ]
            await send(message)

        try:
            await self._app(scope, receive, _send)
        finally:
            correlation_id.reset(token)


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service(settings: SettingsDep, session: SessionDep) -> StatusService:
    return StatusService(
        ServiceRepository(session),
        CheckRepository(session),
        IncidentRepository(session),
        settings,
    )


ServiceDep = Annotated[StatusService, Depends(get_service)]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    if getattr(app.state, "session_factory", None) is None:
        engine = create_engine(settings.database_url, echo=settings.db_echo)
        # Pas d'Alembic dans ce checkpoint (hors DoD) : le schéma est créé au démarrage.
        # En production on utiliserait des migrations (patron : `shorturl` / `taskman`).
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)
        _owns_engine = True
    else:
        _owns_engine = False

    if getattr(app.state, "metrics", None) is None:
        app.state.metrics = Metrics()

    client = httpx.AsyncClient(timeout=settings.probe_timeout_seconds, follow_redirects=True)
    app.state.probe_client = client
    app.state.monitor = Monitor(app.state.session_factory, settings, app.state.metrics, client)

    worker: asyncio.Task[None] | None = None
    if settings.worker_enabled:
        worker = asyncio.create_task(app.state.monitor.run_forever())
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await client.aclose()
        if _owns_engine:
            await app.state.db_engine.dispose()


def _problem(code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"type": "about:blank", "title": detail, "status": code, "detail": detail},
        media_type="application/problem+json",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="statuspage", version=__version__, lifespan=lifespan)
    app.state.settings = settings or get_settings()
    app.add_middleware(CorrelationMiddleware)

    @app.exception_handler(StatusPageError)
    async def _domain(request: Request, exc: StatusPageError) -> JSONResponse:
        return _problem(_ERROR_STATUS.get(type(exc), 400), str(exc) or type(exc).__name__)

    # --- services ----------------------------------------------------
    @app.post("/services", status_code=status.HTTP_201_CREATED, response_model=ServiceRead)
    async def create_service(
        payload: ServiceCreate, service: ServiceDep, session: SessionDep, response: Response
    ) -> ServiceRead:
        created = await service.create_service(
            name=payload.name,
            url=str(payload.url),
            interval_seconds=payload.interval_seconds,
            expected_status=payload.expected_status,
        )
        await session.commit()
        response.headers["Location"] = f"/services/{created.id}"
        return created

    @app.get("/services", response_model=list[ServiceRead])
    async def list_services(service: ServiceDep) -> list[ServiceRead]:
        return await service.list_services()

    @app.get("/services/{service_id}", response_model=ServiceRead)
    async def get_service_(service_id: int, service: ServiceDep) -> ServiceRead:
        return await service.get_service(service_id)

    @app.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_service(service_id: int, service: ServiceDep, session: SessionDep) -> None:
        await service.delete_service(service_id)
        await session.commit()

    @app.get("/services/{service_id}/history", response_model=CheckPage)
    async def service_history(
        service_id: int,
        service: ServiceDep,
        since: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> CheckPage:
        return await service.history(service_id, since=since, limit=limit, offset=offset)

    # --- incidents --------------------------------------------------
    @app.post("/incidents", status_code=status.HTTP_201_CREATED, response_model=IncidentRead)
    async def open_incident(
        payload: IncidentCreate, service: ServiceDep, session: SessionDep
    ) -> IncidentRead:
        created = await service.open_incident(title=payload.title, body=payload.body)
        await session.commit()
        return created

    @app.patch("/incidents/{incident_id}", response_model=IncidentRead)
    async def patch_incident(
        incident_id: int, payload: IncidentUpdate, service: ServiceDep, session: SessionDep
    ) -> IncidentRead:
        updated = await service.update_incident(
            incident_id, title=payload.title, body=payload.body, status=payload.status
        )
        await session.commit()
        return updated

    # --- page d'état ----------------------------------------------
    @app.get("/status", response_model=StatusSummary)
    async def status_page(service: ServiceDep) -> StatusSummary:
        logger.info("agrégation de la page d'état")
        return await service.status_summary()

    # --- exploitation --------------------------------------------
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready(request: Request) -> Response:
        problems: list[str] = []
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            problems.append("database")

        monitor: Monitor = request.app.state.monitor
        settings: Settings = request.app.state.settings
        if settings.worker_enabled:
            staleness = settings.ready_max_worker_staleness_seconds
            if monitor.last_run_at is None:
                problems.append("worker-not-started")
            elif (datetime.now(UTC) - monitor.last_run_at).total_seconds() > staleness:
                problems.append("worker-stale")

        if problems:
            return JSONResponse({"status": "unavailable", "problems": problems}, status_code=503)
        return JSONResponse({"status": "ready"})

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        body, content_type = request.app.state.metrics.render()
        return PlainTextResponse(body, media_type=content_type)

    return app


app = create_app()
