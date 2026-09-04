"""Couche HTTP : routes fines, traduction des erreurs métier en codes HTTP."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shorturl import __version__
from shorturl.config import Settings, get_settings
from shorturl.db import create_engine, create_session_factory, get_session
from shorturl.errors import (
    AliasGenerationError,
    AliasTakenError,
    LinkExpiredError,
    LinkNotFoundError,
)
from shorturl.repository import LinkRepository
from shorturl.schemas import LinkCreate, LinkCreated, LinkStats
from shorturl.service import LinkService

logger = logging.getLogger("shorturl")

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service(settings: SettingsDep, session: SessionDep) -> LinkService:
    return LinkService(LinkRepository(session), settings)


ServiceDep = Annotated[LinkService, Depends(get_service)]


async def _increment_click(app: FastAPI, alias: str) -> None:
    """Tâche de fond : session dédiée, échec isolé (la redirection est déjà partie)."""
    try:
        async with app.state.session_factory() as session:
            await LinkRepository(session).register_click(alias)
            await session.commit()
    except Exception:
        logger.warning("échec de l'incrément de clics pour %s", alias, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Les tests pré-remplissent `session_factory` avec une base jetable : on n'ouvre alors
    # aucun moteur « de production ».
    if getattr(app.state, "session_factory", None) is None:
        settings = get_settings()
        engine = create_engine(settings.database_url, echo=settings.db_echo)
        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()
    else:
        yield


def _problem(code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"type": "about:blank", "title": detail, "status": code, "detail": detail},
        media_type="application/problem+json",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="shorturl", version=__version__, lifespan=lifespan)
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

    @app.exception_handler(LinkNotFoundError)
    async def _nf(request: Request, exc: LinkNotFoundError) -> JSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Lien introuvable")

    @app.exception_handler(LinkExpiredError)
    async def _gone(request: Request, exc: LinkExpiredError) -> JSONResponse:
        return _problem(status.HTTP_410_GONE, "Ce lien a expiré")

    @app.exception_handler(AliasTakenError)
    async def _taken(request: Request, exc: AliasTakenError) -> JSONResponse:
        return _problem(status.HTTP_409_CONFLICT, f"Alias déjà pris : {exc}")

    @app.exception_handler(AliasGenerationError)
    async def _genfail(request: Request, exc: AliasGenerationError) -> JSONResponse:
        return _problem(status.HTTP_503_SERVICE_UNAVAILABLE, "Impossible de générer un alias")

    @app.post("/links", status_code=status.HTTP_201_CREATED, response_model=LinkCreated)
    async def create_link(
        payload: LinkCreate, service: ServiceDep, session: SessionDep
    ) -> LinkCreated:
        row = await service.create(
            target_url=str(payload.url),
            custom_alias=payload.custom_alias,
            expires_at=payload.expires_at,
        )
        await session.commit()
        return LinkCreated(
            alias=row.alias,
            short_url=service.short_url(row.alias),
            target_url=row.target_url,
            expires_at=row.expires_at,
        )

    @app.get("/links/{alias}/stats", response_model=LinkStats)
    async def link_stats(alias: str, service: ServiceDep) -> LinkStats:
        return LinkStats.model_validate(await service.stats(alias))

    @app.delete("/links/{alias}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_link(alias: str, service: ServiceDep, session: SessionDep) -> None:
        await service.delete(alias)
        await session.commit()

    @app.get("/{alias}")
    async def resolve_link(
        alias: str, service: ServiceDep, request: Request, background: BackgroundTasks
    ) -> RedirectResponse:
        target = await service.resolve(alias)
        background.add_task(_increment_click, request.app, alias)
        return RedirectResponse(target, status_code=status.HTTP_302_FOUND)

    return app


app = create_app()
