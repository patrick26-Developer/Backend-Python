"""Schémas des utilisateurs et des jetons (Module 06)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRole(StrEnum):
    admin = "admin"
    member = "member"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, examples=["un-mot-de-passe-solide"])


class UserRead(BaseModel):
    """Sortie publique — **jamais** le hash du mot de passe."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
