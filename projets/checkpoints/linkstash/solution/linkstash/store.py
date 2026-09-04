"""Store en mémoire (pas de base de données à ce checkpoint).

`BookmarkStore` encapsule la structure de données ET les règles d'unicité / de tri /
de filtrage — la couche API ne manipule jamais le `dict` directement.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from linkstash.models import BookmarkCreate, BookmarkUpdate, SortKey


class DuplicateURLError(Exception):
    """L'URL est déjà enregistrée (→ 409)."""


class BookmarkNotFoundError(Exception):
    """Aucun marque-page pour cet id (→ 404)."""


@dataclass
class Bookmark:
    id: int
    url: str
    title: str
    note: str | None
    tags: list[str]
    favorite: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _canonical(url: str) -> str:
    """Clé de comparaison d'unicité : insensible à la casse du schéma/hôte, sans « / » final."""
    return url.strip().rstrip("/").lower()


def _sort_key(sort: SortKey) -> tuple[Callable[[Bookmark], Any], bool]:
    """(fonction de clé, ordre décroissant) pour chaque valeur de tri."""
    if sort in ("-created_at", "created_at"):
        return (lambda b: b.created_at, sort.startswith("-"))
    # tri de titre insensible à la casse ("alpha" avant "Bravo")
    return (lambda b: b.title.lower(), sort.startswith("-"))


class BookmarkStore:
    def __init__(self) -> None:
        self._items: dict[int, Bookmark] = {}
        self._ids = itertools.count(1)

    # --- écritures --------------------------------------------------------
    def add(self, data: BookmarkCreate) -> Bookmark:
        url = str(data.url)
        if any(_canonical(b.url) == _canonical(url) for b in self._items.values()):
            raise DuplicateURLError(url)
        bookmark = Bookmark(
            id=next(self._ids),
            url=url,
            title=data.title,
            note=data.note,
            tags=list(data.tags),
            favorite=data.favorite,
        )
        self._items[bookmark.id] = bookmark
        return bookmark

    def update(self, bookmark_id: int, patch: BookmarkUpdate) -> Bookmark:
        bookmark = self.get(bookmark_id)
        changes = patch.model_dump(exclude_unset=True)
        if "url" in changes:
            new_url = str(patch.url)
            clash = any(
                b.id != bookmark_id and _canonical(b.url) == _canonical(new_url)
                for b in self._items.values()
            )
            if clash:
                raise DuplicateURLError(new_url)
            bookmark.url = new_url
        if "title" in changes:
            bookmark.title = changes["title"]
        if "note" in changes:  # présent même si `None` → efface
            bookmark.note = changes["note"]
        if "tags" in changes:
            bookmark.tags = changes["tags"]
        if "favorite" in changes:
            bookmark.favorite = changes["favorite"]
        return bookmark

    def delete(self, bookmark_id: int) -> None:
        if self._items.pop(bookmark_id, None) is None:
            raise BookmarkNotFoundError(bookmark_id)

    # --- lectures --------------------------------------------------------
    def get(self, bookmark_id: int) -> Bookmark:
        try:
            return self._items[bookmark_id]
        except KeyError as exc:
            raise BookmarkNotFoundError(bookmark_id) from exc

    def list_page(
        self,
        *,
        tag: str | None = None,
        favorite: bool | None = None,
        q: str | None = None,
        sort: SortKey = "-created_at",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Bookmark], int]:
        rows = list(self._items.values())
        if tag is not None:
            needle = tag.strip().lower()
            rows = [b for b in rows if needle in b.tags]
        if favorite is not None:
            rows = [b for b in rows if b.favorite is favorite]
        if q:
            needle = q.strip().lower()
            rows = [
                b
                for b in rows
                if needle in b.title.lower() or (b.note is not None and needle in b.note.lower())
            ]

        key_fn, reverse = _sort_key(sort)
        # tri secondaire stable sur l'id pour un ordre déterministe à valeurs égales
        rows.sort(key=lambda b: b.id, reverse=reverse)
        rows.sort(key=key_fn, reverse=reverse)

        total = len(rows)
        return rows[offset : offset + limit], total

    def tag_counts(self) -> list[tuple[str, int]]:
        counter: Counter[str] = Counter()
        for bookmark in self._items.values():
            counter.update(bookmark.tags)
        # tri : plus fréquent d'abord, puis alphabétique
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
