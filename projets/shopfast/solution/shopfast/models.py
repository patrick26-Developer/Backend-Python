"""Tables. `OrderItemRow.unit_price` = **snapshot** du prix à la commande (jamais recalculé)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopfast.db import Base, TZDateTime


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="customer")  # customer | admin
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())


class CartItemRow(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_items_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer)


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending -> paid -> shipped -> delivered ; pending/paid -> cancelled ; paid -> refunded
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now(), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)

    items: Mapped[list[OrderItemRow]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    payment: Mapped[PaymentRow | None] = relationship(
        back_populates="order", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class OrderItemRow(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(200))  # snapshot
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot — NE bouge jamais
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[OrderRow] = relationship(back_populates="items")


class PaymentRow(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    intent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="requires_payment")
    # requires_payment -> succeeded | failed
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[OrderRow] = relationship(back_populates="payment")


class ProcessedWebhookRow(Base):
    """Journal d'idempotence des webhooks : `event_id` déjà vu → on ignore le rejeu."""

    __tablename__ = "processed_webhooks"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())
