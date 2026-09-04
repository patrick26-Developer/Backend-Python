"""Contrats d'API (Pydantic v2). Séparés du modèle ORM."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")


class LinkCreate(BaseModel):
    url: AnyHttpUrl
    custom_alias: str | None = Field(
        default=None, description="de 3 à 32 caractères : lettres, chiffres, tiret, underscore"
    )
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def _valid_alias(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _ALIAS_RE.match(v):
            raise ValueError("alias invalide : ^[a-zA-Z0-9_-]{3,32}$")
        return v

    @field_validator("expires_at")
    @classmethod
    def _future(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("expires_at doit être une date/heure avec fuseau (UTC)")
        return v


class LinkCreated(BaseModel):
    alias: str
    short_url: str
    target_url: str
    expires_at: datetime | None


class LinkStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alias: str
    target_url: str
    clicks: int
    created_at: datetime
    last_clicked_at: datetime | None
    expires_at: datetime | None
