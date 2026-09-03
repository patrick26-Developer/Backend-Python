"""Primitives de sécurité : hachage de mots de passe (argon2) et JSON Web Tokens.

Aucune connaissance de FastAPI ni de la base ici — juste de la crypto et du JWT.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Paramètres argon2id recommandés par l'OWASP (Password Storage Cheat Sheet) :
# t=2, m≈19 Mio, p=1 — solide et raisonnablement rapide (~150 ms).
_hasher = PasswordHash([Argon2Hasher(time_cost=2, memory_cost=19_456, parallelism=1)])

TokenType = Literal["access", "refresh"]


# --- Mots de passe ---------------------------------------------------------


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    # comparaison en temps constant, gérée par pwdlib
    return _hasher.verify(plain, hashed)


# --- JWT -----------------------------------------------------------------


def create_token(
    *,
    subject: str,
    token_type: TokenType,
    secret: str,
    algorithm: str,
    expires_in: timedelta,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Renvoie (token_encodé, jti). `jti` = identifiant unique du token
    (utile pour révoquer un refresh token)."""
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm), jti


def decode_token(token: str, *, secret: str, algorithms: list[str]) -> dict[str, Any]:
    """Lève `jwt.InvalidTokenError` (et sous-classes : `ExpiredSignatureError`…)
    si le token est invalide, expiré ou altéré."""
    decoded: dict[str, Any] = jwt.decode(token, secret, algorithms=algorithms)
    return decoded
