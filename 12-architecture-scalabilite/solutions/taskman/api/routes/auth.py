"""Routes d'authentification : inscription, connexion, rafraîchissement, profil."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from taskman.api.deps import AuthServiceDep, CurrentUser
from taskman.api.ratelimit import auth_rate_limit
from taskman.schemas import RefreshRequest, TokenPair, UserCreate, UserRead

# Rate limiting par IP sur TOUTES les routes de ce router (anti-brute force).
router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_rate_limit)])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, auth: AuthServiceDep) -> UserRead:
    return await auth.register(payload)


@router.post("/login")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
) -> TokenPair:
    # OAuth2 password flow : `username` = l'e-mail ici.
    return await auth.login(email=form.username, password=form.password)


@router.post("/refresh")
async def refresh(payload: RefreshRequest, auth: AuthServiceDep) -> TokenPair:
    return await auth.refresh(payload.refresh_token)


@router.get("/me")
async def me(user: CurrentUser) -> UserRead:
    return user
