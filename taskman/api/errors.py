"""Traduction des exceptions en réponses HTTP **normalisées** (RFC 9457 — Problem
Details).

Toutes les erreurs de l'API sortent avec le **même** schéma JSON :

    {
      "type": "about:blank",
      "title": "Ressource introuvable",
      "status": 404,
      "detail": "Tâche 42 introuvable",
      "code": "task_not_found",
      "instance": "/tasks/42",
      "request_id": "9f3c…"
    }

`Content-Type: application/problem+json`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from taskman.core.context import get_request_id
from taskman.core.exceptions import DomainError

_logger = logging.getLogger("taskman.error")

PROBLEM_JSON = "application/problem+json"


def _problem(
    *, status: int, title: str, detail: str, code: str, instance: str, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "instance": instance,
    }
    rid = get_request_id()
    if rid is not None:
        body["request_id"] = rid
    body.update(extra)
    # jsonable_encoder : gère datetime, Decimal, et les objets non sérialisables
    # que Pydantic met dans les détails d'erreur de validation.
    return JSONResponse(jsonable_encoder(body), status_code=status, media_type=PROBLEM_JSON)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            code=exc.code,
            instance=request.url.path,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            status=422,
            title="Requête invalide",
            detail="La requête n'a pas passé la validation.",
            code="validation_error",
            instance=request.url.path,
            errors=exc.errors(),
        )  # `errors` est nettoyé par jsonable_encoder dans _problem()

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(
            status=exc.status_code,
            title=str(exc.detail),
            detail=str(exc.detail),
            code="http_error",
            instance=request.url.path,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # On loggue TOUT (stack incluse) côté serveur, on ne fuit RIEN au client.
        _logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return _problem(
            status=500,
            title="Erreur interne",
            detail="Une erreur inattendue est survenue.",
            code="internal_error",
            instance=request.url.path,
        )
