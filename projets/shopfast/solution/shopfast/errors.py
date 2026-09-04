"""Erreurs métier — découplées de HTTP (traduites en `api/errors`)."""

from __future__ import annotations


class ShopError(Exception):
    """Base."""


class NotFoundError(ShopError):
    """→ 404."""


class ConflictError(ShopError):
    """→ 409."""


class OutOfStockError(ConflictError):
    """Stock insuffisant pour un article."""


class EmptyCartError(ShopError):
    """Checkout d'un panier vide → 400."""


class InvalidTransitionError(ConflictError):
    """Transition de statut de commande illégale."""


class AuthError(ShopError):
    """→ 401."""


class ForbiddenError(ShopError):
    """→ 403."""
