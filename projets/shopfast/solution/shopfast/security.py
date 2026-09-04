"""Hachage de mot de passe (argon2id, paramètres OWASP) + JWT d'accès (pyjwt)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Paramètres OWASP (≈ 150 ms/hash) — PAS `.recommended()` (bien trop lent pour une suite).
_hasher = PasswordHash([Argon2Hasher(time_cost=2, memory_cost=19_456, parallelism=1)])


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def create_access_token(
    *, subject: str, role: str, secret: str, algorithm: str, expires_minutes: int
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str, algorithm: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[algorithm])
