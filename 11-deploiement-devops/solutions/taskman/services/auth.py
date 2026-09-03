"""Couche métier de l'authentification.

- inscription (hachage argon2, e-mail unique) ;
- connexion (vérification en temps constant, protection contre l'énumération) ;
- jetons JWT : access court + refresh long, avec **rotation** (à chaque refresh,
  l'ancien refresh token est révoqué) et révocation possible (table `refresh_tokens`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt

from taskman.core import security  # accès via le module -> monkeypatchable en test
from taskman.core.config import Settings
from taskman.core.exceptions import InvalidCredentialsError, InvalidTokenError
from taskman.core.security import create_token, decode_token
from taskman.db.models import UserRow
from taskman.repositories import RefreshTokenRepository, UnitOfWork, UserRepository
from taskman.schemas import TokenPair, UserCreate, UserRead


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash « bidon » vérifié quand l'utilisateur n'existe pas, pour que le temps
    de réponse ne trahisse pas l'existence d'un compte (timing attack).
    Calculé à la 1re demande (et non à l'import) pour rester monkeypatchable."""
    return security.hash_password("x" * 24)


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        uow: UnitOfWork,
        settings: Settings,
    ) -> None:
        self._users = users
        self._refresh = refresh_tokens
        self._uow = uow
        self._settings = settings

    # --- inscription ---------------------------------------------------
    async def register(self, data: UserCreate) -> UserRead:
        row = await self._users.create(
            email=data.email, hashed_password=security.hash_password(data.password)
        )
        await self._uow.commit()
        return UserRead.model_validate(row)

    # --- connexion ---------------------------------------------------
    async def login(self, *, email: str, password: str) -> TokenPair:
        user = await self._users.get_by_email(email)
        stored = user.hashed_password if user is not None else _dummy_hash()
        if not security.verify_password(password, stored) or user is None:
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InvalidTokenError("Compte désactivé")
        return await self._issue_pair(user)

    # --- rafraîchissement (avec rotation) -----------------------------
    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = self._decode(refresh_token, expected_type="refresh")
        jti = str(payload["jti"])
        stored = await self._refresh.get(jti)
        if stored is None or stored.revoked or _expired(stored.expires_at):
            raise InvalidTokenError("Refresh token invalide ou révoqué")

        user = await self._users.get(int(str(payload["sub"])))
        if user is None or not user.is_active:
            raise InvalidTokenError("Utilisateur introuvable ou inactif")

        await self._refresh.revoke(jti)  # rotation : l'ancien ne resservira pas
        return await self._issue_pair(user)

    # --- résolution de l'utilisateur courant (depuis l'access token) ---
    async def user_from_access_token(self, token: str) -> UserRow:
        payload = self._decode(token, expected_type="access")
        user = await self._users.get(int(str(payload["sub"])))
        if user is None or not user.is_active:
            raise InvalidTokenError("Utilisateur introuvable ou inactif")
        return user

    # --- interne -----------------------------------------------------
    def _decode(self, token: str, *, expected_type: str) -> dict[str, object]:
        try:
            payload = decode_token(
                token,
                secret=self._settings.jwt_secret_key.get_secret_value(),
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError() from exc
        if payload.get("type") != expected_type:
            raise InvalidTokenError(f"Type de jeton attendu : {expected_type}")
        return payload

    async def _issue_pair(self, user: UserRow) -> TokenPair:
        secret = self._settings.jwt_secret_key.get_secret_value()
        alg = self._settings.jwt_algorithm

        access, _ = create_token(
            subject=str(user.id),
            token_type="access",
            secret=secret,
            algorithm=alg,
            expires_in=timedelta(minutes=self._settings.access_token_expire_minutes),
            extra={"role": user.role.value},
        )
        refresh_ttl = timedelta(days=self._settings.refresh_token_expire_days)
        refresh, jti = create_token(
            subject=str(user.id),
            token_type="refresh",
            secret=secret,
            algorithm=alg,
            expires_in=refresh_ttl,
        )
        await self._refresh.add(
            jti=jti, user_id=user.id, expires_at=datetime.now(UTC) + refresh_ttl
        )
        await self._uow.commit()
        return TokenPair(access_token=access, refresh_token=refresh)


def _expired(when: datetime) -> bool:
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when < datetime.now(UTC)
