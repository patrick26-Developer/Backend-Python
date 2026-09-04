"""Accès données. Le point sensible : `try_reserve_stock` (décrément atomique conditionnel)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shopfast.errors import ConflictError
from shopfast.models import (
    CartItemRow,
    OrderRow,
    ProcessedWebhookRow,
    ProductRow,
    UserRow,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, email: str, password_hash: str, role: str = "customer") -> UserRow:
        row = UserRow(email=email, password_hash=password_hash, role=role)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError("email déjà enregistré") from exc
        return row

    async def by_email(self, email: str) -> UserRow | None:
        return (
            await self._session.scalars(select(UserRow).where(UserRow.email == email))
        ).one_or_none()

    async def by_id(self, user_id: int) -> UserRow | None:
        return await self._session.get(UserRow, user_id)


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, sku: str, name: str, price: Decimal, stock: int) -> ProductRow:
        row = ProductRow(sku=sku, name=name, price=price, stock=stock)
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(f"SKU déjà utilisé : {sku}") from exc
        return row

    async def get(self, product_id: int) -> ProductRow | None:
        return await self._session.get(ProductRow, product_id)

    async def list_active(self) -> list[ProductRow]:
        return list(
            (
                await self._session.scalars(
                    select(ProductRow).where(ProductRow.active.is_(True)).order_by(ProductRow.name)
                )
            ).all()
        )

    async def set_price(self, product_id: int, price: Decimal) -> None:
        await self._session.execute(
            update(ProductRow).where(ProductRow.id == product_id).values(price=price)
        )

    async def try_reserve_stock(self, product_id: int, quantity: int) -> bool:
        """Décrément **atomique et conditionnel** : `... WHERE stock >= :q`.

        Renvoie `True` si la réservation a réussi. Deux acheteurs sur le dernier article :
        un seul `UPDATE` touche une ligne, l'autre touche 0 → un seul réussit. Aucune
        lecture-puis-écriture, donc aucune fenêtre de course (vrai sur PostgreSQL ;
        sérialisé sur SQLite mais le chemin de code est identique)."""
        result: CursorResult[Any] = await self._session.execute(  # type: ignore[assignment]
            update(ProductRow)
            .where(ProductRow.id == product_id, ProductRow.stock >= quantity)
            .values(stock=ProductRow.stock - quantity)
        )
        return (result.rowcount or 0) == 1

    async def release_stock(self, product_id: int, quantity: int) -> None:
        await self._session.execute(
            update(ProductRow)
            .where(ProductRow.id == product_id)
            .values(stock=ProductRow.stock + quantity)
        )


class CartRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def items(self, user_id: int) -> list[CartItemRow]:
        return list(
            (
                await self._session.scalars(
                    select(CartItemRow)
                    .where(CartItemRow.user_id == user_id)
                    .order_by(CartItemRow.id)
                )
            ).all()
        )

    async def upsert(self, user_id: int, product_id: int, quantity: int) -> None:
        existing = (
            await self._session.scalars(
                select(CartItemRow).where(
                    CartItemRow.user_id == user_id, CartItemRow.product_id == product_id
                )
            )
        ).one_or_none()
        if existing is None:
            self._session.add(
                CartItemRow(user_id=user_id, product_id=product_id, quantity=quantity)
            )
        else:
            existing.quantity = quantity
        await self._session.flush()

    async def remove(self, user_id: int, product_id: int) -> None:
        await self._session.execute(
            delete(CartItemRow).where(
                CartItemRow.user_id == user_id, CartItemRow.product_id == product_id
            )
        )

    async def clear(self, user_id: int) -> None:
        await self._session.execute(delete(CartItemRow).where(CartItemRow.user_id == user_id))


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, order: OrderRow) -> None:
        self._session.add(order)

    async def get_for_user(self, order_id: int, user_id: int) -> OrderRow | None:
        """Filtre par `user_id` **dans la requête** : un client ne peut pas voir la commande
        d'un autre (retour `None` → 404, jamais 403 qui divulguerait l'existence)."""
        return (
            await self._session.scalars(
                select(OrderRow).where(OrderRow.id == order_id, OrderRow.user_id == user_id)
            )
        ).one_or_none()

    async def get_any(self, order_id: int) -> OrderRow | None:
        return await self._session.get(OrderRow, order_id)

    async def list_for_user(self, user_id: int) -> list[OrderRow]:
        return list(
            (
                await self._session.scalars(
                    select(OrderRow)
                    .where(OrderRow.user_id == user_id)
                    .order_by(OrderRow.created_at.desc())
                )
            ).all()
        )

    async def by_intent(self, intent_id: str) -> OrderRow | None:
        from shopfast.models import PaymentRow

        return (
            await self._session.scalars(
                select(OrderRow).join(PaymentRow).where(PaymentRow.intent_id == intent_id)
            )
        ).one_or_none()


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def mark_processed(self, event_id: str) -> bool:
        """`True` si c'est la 1re fois qu'on voit cet `event_id` ; `False` si c'est un rejeu."""
        self._session.add(ProcessedWebhookRow(event_id=event_id))
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True
