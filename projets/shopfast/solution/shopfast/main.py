"""`create_app()` : factory, lifespan, traduction des erreurs métier en Problem Details."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shopfast import __version__
from shopfast.config import Settings, get_settings
from shopfast.db import Base, create_engine, create_session_factory
from shopfast.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ShopError,
)
from shopfast.models import (  # noqa: F401  (enregistre les tables auprès de Base.metadata)
    CartItemRow,
    OrderItemRow,
    OrderRow,
    PaymentRow,
    ProcessedWebhookRow,
    ProductRow,
    UserRow,
)
from shopfast.routes import router

_STATUS: list[tuple[type[ShopError], int]] = [
    (NotFoundError, 404),
    (ForbiddenError, 403),
    (AuthError, 401),
    (ConflictError, 409),  # couvre OutOfStockError, InvalidTransitionError
    (ShopError, 400),  # fallback (EmptyCartError…)
]


def _status_for(exc: ShopError) -> int:
    for kind, code in _STATUS:
        if isinstance(exc, kind):
            return code
    return 400


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if getattr(app.state, "session_factory", None) is None:
        engine = create_engine(settings.database_url, echo=settings.db_echo)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)  # dev ; prod = migrations Alembic
        app.state.db_engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            await engine.dispose()
    else:
        yield


def _problem(code: int, detail: str, *, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"type": "about:blank", "title": detail, "status": code, "detail": detail},
        media_type="application/problem+json",
        headers=headers,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="shopfast", version=__version__, lifespan=lifespan)
    app.state.settings = settings or get_settings()

    @app.exception_handler(ShopError)
    async def _shop_error(request: Request, exc: ShopError) -> JSONResponse:
        code = _status_for(exc)
        headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
        return _problem(code, str(exc) or type(exc).__name__, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "type": "about:blank",
                "title": "requête invalide",
                "status": 422,
                "errors": jsonable_encoder(exc.errors()),
            },
            media_type="application/problem+json",
        )

    app.include_router(router)
    return app


app = create_app()
