"""Tests unitaires : sécurité (hachage, JWT) + AuthService (avec repos en mémoire)."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from taskman.core.config import Settings
from taskman.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from taskman.core.security import create_token, decode_token, hash_password, verify_password
from taskman.repositories import (
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
    NullUnitOfWork,
)
from taskman.schemas import UserCreate
from taskman.services import AuthService

SECRET = "test-secret-least-32-bytes-long-000000"


# --- primitives -------------------------------------------------
def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"  # jamais en clair
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip_and_tamper() -> None:
    token, jti = create_token(
        subject="42",
        token_type="access",
        secret=SECRET,
        algorithm="HS256",
        expires_in=timedelta(minutes=5),
    )
    payload = decode_token(token, secret=SECRET, algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert payload["jti"] == jti
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token + "x", secret=SECRET, algorithms=["HS256"])
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, secret="a-different-secret-also-32-bytes-min", algorithms=["HS256"])


def test_jwt_expired() -> None:
    token, _ = create_token(
        subject="1",
        token_type="access",
        secret=SECRET,
        algorithm="HS256",
        expires_in=timedelta(seconds=-1),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, secret=SECRET, algorithms=["HS256"])


# --- AuthService -----------------------------------------------
def _service() -> AuthService:
    return AuthService(
        InMemoryUserRepository(),
        InMemoryRefreshTokenRepository(),
        NullUnitOfWork(),
        Settings(env="test", jwt_secret_key=SECRET),  # type: ignore[arg-type]
    )


async def test_register_then_login() -> None:
    auth = _service()
    user = await auth.register(UserCreate(email="a@x.co", password="password12345"))
    assert user.email == "a@x.co"
    pair = await auth.login(email="a@x.co", password="password12345")
    assert pair.access_token and pair.refresh_token


async def test_register_duplicate_raises() -> None:
    auth = _service()
    await auth.register(UserCreate(email="d@x.co", password="password12345"))
    with pytest.raises(EmailAlreadyRegisteredError):
        await auth.register(UserCreate(email="d@x.co", password="password12345"))


async def test_login_wrong_password_raises() -> None:
    auth = _service()
    await auth.register(UserCreate(email="w@x.co", password="password12345"))
    with pytest.raises(InvalidCredentialsError):
        await auth.login(email="w@x.co", password="nope")


async def test_login_unknown_user_raises_same_error() -> None:
    with pytest.raises(InvalidCredentialsError):
        await _service().login(email="ghost@x.co", password="whatever12345")


async def test_refresh_rotation_invalidates_old() -> None:
    auth = _service()
    await auth.register(UserCreate(email="r@x.co", password="password12345"))
    pair = await auth.login(email="r@x.co", password="password12345")

    new_pair = await auth.refresh(pair.refresh_token)
    assert new_pair.refresh_token != pair.refresh_token

    with pytest.raises(InvalidTokenError):
        await auth.refresh(pair.refresh_token)  # l'ancien est révoqué


async def test_access_token_not_accepted_as_refresh() -> None:
    auth = _service()
    await auth.register(UserCreate(email="x@x.co", password="password12345"))
    pair = await auth.login(email="x@x.co", password="password12345")
    with pytest.raises(InvalidTokenError):
        await auth.refresh(pair.access_token)
