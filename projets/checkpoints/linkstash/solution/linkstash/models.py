"""Schémas Pydantic : contrats d'entrée / sortie strictement séparés.

- `BookmarkCreate` : corps de `POST /bookmarks`.
- `BookmarkUpdate` : corps de `PATCH /bookmarks/{id}` — tout optionnel, `null` explicite géré.
- `BookmarkRead`   : ce que l'API renvoie (ajoute `id` + `created_at`).
- `BookmarkPage`   : enveloppe de pagination.
- `TagCount`       : ligne de `GET /tags`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SortKey = Literal["-created_at", "created_at", "title", "-title"]

_MAX_TAGS = 15
_TAG_MIN, _TAG_MAX = 1, 30


def _normalize_tags(tags: list[str]) -> list[str]:
    """Minuscules, sans espaces, dédupliquées en gardant l'ordre, bornées en nombre/longueur."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not (_TAG_MIN <= len(tag) <= _TAG_MAX):
            raise ValueError(f"tag invalide : {raw!r} ({_TAG_MIN} à {_TAG_MAX} caractères)")
        if tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    if len(cleaned) > _MAX_TAGS:
        raise ValueError(f"au plus {_MAX_TAGS} tags")
    return cleaned


class BookmarkBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000, description="Markdown court")
    tags: list[str] = Field(default_factory=list)
    favorite: bool = False

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v

    @field_validator("note")
    @classmethod
    def _note_blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str]) -> list[str]:
        return _normalize_tags(tags)


class BookmarkCreate(BookmarkBase):
    url: AnyHttpUrl = Field(description="URL du marque-page (http/https, validée)")


class BookmarkUpdate(BaseModel):
    """`PATCH` : seuls les champs présents sont modifiés.

    - `url` / `title` : optionnels mais NON nullables (on ne peut pas les effacer).
    - `note` : nullable — `{"note": null}` efface la note.
    """

    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    favorite: bool | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v

    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str] | None) -> list[str] | None:
        return None if tags is None else _normalize_tags(tags)

    @model_validator(mode="after")
    def _reject_null_on_non_nullable(self) -> BookmarkUpdate:
        provided = self.model_fields_set
        for field in ("url", "title"):
            if field in provided and getattr(self, field) is None:
                raise ValueError(f"{field} ne peut pas être mis à null")
        return self


class BookmarkRead(BookmarkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str  # déjà validée à la création ; stockée en chaîne canonique
    created_at: datetime


class BookmarkPage(BaseModel):
    items: list[BookmarkRead]
    total: int
    limit: int
    offset: int


class TagCount(BaseModel):
    tag: str
    count: int
