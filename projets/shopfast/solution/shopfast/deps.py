"""Dépendances FastAPI : session, services, utilisateur courant, RBAC."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shopfast.config import Settings, get_settings
from shopfast.db import get_session
from shopfast.errors import AuthError, ForbiddenError, NotFoundError
from shopfast.models import UserRow
from shopfast.repositories import (
    CartRepository,
    OrderRepository,
    ProductRepository,
    UserRepository,
    WebhookRepository,
)
from shopfast.security import decode_token
from shopfast.services import (
    AuthService,
    CartService,
    CatalogService,
    CheckoutService,
    OrderService,
    WebhookService,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str | None, Depends(oauth2_scheme)]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(UserRepository(session), settings)


def get_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(ProductRepository(session))


def get_cart_service(session: SessionDep) -> CartService:
    return CartService(CartRepository(session), ProductRepository(session))


def get_checkout_service(session: SessionDep) -> CheckoutService:
    return CheckoutService(
        CartRepository(session), ProductRepository(session), OrderRepository(session)
    )


def get_order_service(session: SessionDep) -> OrderService:
    return OrderService(OrderRepository(session), ProductRepository(session))


def get_webhook_service(session: SessionDep) -> WebhookService:
    return WebhookService(
        WebhookRepository(session), OrderRepository(session), ProductRepository(session)
    )


async def get_current_user(token: TokenDep, session: SessionDep, settings: SettingsDep) -> UserRow:
    if not token:
        raise AuthError("jeton manquant")
    try:
        payload = decode_token(
            token,
            secret=settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError("jeton invalide") from exc
    user = await UserRepository(session).by_id(int(payload["sub"]))
    if user is None:
        raise AuthError("utilisateur inconnu")
    return user


CurrentUser = Annotated[UserRow, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> UserRow:
    if user.role != "admin":
        raise ForbiddenError("réservé aux administrateurs")
    return user


AdminUser = Annotated[UserRow, Depends(require_admin)]

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
CartServiceDep = Annotated[CartService, Depends(get_cart_service)]
CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]
OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
WebhookServiceDep = Annotated[WebhookService, Depends(get_webhook_service)]

__all__ = [
    "AdminUser",
    "AuthServiceDep",
    "CartServiceDep",
    "CatalogServiceDep",
    "CheckoutServiceDep",
    "CurrentUser",
    "NotFoundError",
    "OrderServiceDep",
    "SessionDep",
    "WebhookServiceDep",
]
