"""Couche HTTP : routes fines, aucune logique métier (elle est dans le store).

`create_app()` (factory) permet à chaque test d'avoir un store neuf sans variable globale.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse

from linkstash import __version__
from linkstash.models import (
    BookmarkCreate,
    BookmarkPage,
    BookmarkRead,
    BookmarkUpdate,
    SortKey,
    TagCount,
)
from linkstash.store import BookmarkNotFoundError, BookmarkStore, DuplicateURLError


def get_store(request: Request) -> BookmarkStore:
    store: BookmarkStore = request.app.state.store
    return store


StoreDep = Annotated[BookmarkStore, Depends(get_store)]

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BookmarkRead)
def create_bookmark(
    payload: BookmarkCreate, store: StoreDep, request: Request, response: Response
) -> BookmarkRead:
    bookmark = store.add(payload)
    response.headers["Location"] = request.url_for("get_bookmark", bookmark_id=bookmark.id).path
    return BookmarkRead.model_validate(bookmark)


@router.get("", response_model=BookmarkPage)
def list_bookmarks(
    store: StoreDep,
    tag: Annotated[str | None, Query(max_length=30)] = None,
    favorite: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: SortKey = "-created_at",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BookmarkPage:
    rows, total = store.list_page(
        tag=tag, favorite=favorite, q=q, sort=sort, limit=limit, offset=offset
    )
    return BookmarkPage(
        items=[BookmarkRead.model_validate(b) for b in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{bookmark_id}", response_model=BookmarkRead)
def get_bookmark(bookmark_id: int, store: StoreDep) -> BookmarkRead:
    return BookmarkRead.model_validate(store.get(bookmark_id))


@router.patch("/{bookmark_id}", response_model=BookmarkRead)
def update_bookmark(bookmark_id: int, patch: BookmarkUpdate, store: StoreDep) -> BookmarkRead:
    return BookmarkRead.model_validate(store.update(bookmark_id, patch))


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark_id: int, store: StoreDep) -> None:
    store.delete(bookmark_id)


tags_router = APIRouter(tags=["tags"])


@tags_router.get("/tags", response_model=list[TagCount])
def list_tags(store: StoreDep) -> list[TagCount]:
    return [TagCount(tag=tag, count=count) for tag, count in store.tag_counts()]


def _problem(code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"type": "about:blank", "title": detail, "status": code, "detail": detail},
        media_type="application/problem+json",
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="linkstash",
        version=__version__,
        summary="API de marque-pages personnels (checkpoint Module 02).",
    )
    app.state.store = BookmarkStore()

    @app.exception_handler(BookmarkNotFoundError)
    async def _not_found(request: Request, exc: BookmarkNotFoundError) -> JSONResponse:
        return _problem(status.HTTP_404_NOT_FOUND, "Marque-page introuvable")

    @app.exception_handler(DuplicateURLError)
    async def _duplicate(request: Request, exc: DuplicateURLError) -> JSONResponse:
        return _problem(status.HTTP_409_CONFLICT, f"URL déjà enregistrée : {exc}")

    app.include_router(router)
    app.include_router(tags_router)
    return app


app = create_app()
