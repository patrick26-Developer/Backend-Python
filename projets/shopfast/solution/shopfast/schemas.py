"""Contrats d'API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- auth ---------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- catalogue --------------------------------------------------------
class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    price: Decimal
    stock: int
    active: bool


# --- panier -----------------------------------------------------------
class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=999)


class CartLine(BaseModel):
    product_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class CartRead(BaseModel):
    items: list[CartLine]
    total: Decimal


# --- commandes ------------------------------------------------------
OrderStatus = Literal["pending", "paid", "shipped", "delivered", "cancelled", "refunded"]


class OrderLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total: Decimal
    created_at: datetime
    paid_at: datetime | None
    items: list[OrderLine]


class PaymentIntentRead(BaseModel):
    intent_id: str
    amount: Decimal
    status: str


class WebhookEvent(BaseModel):
    """Événement envoyé par le PSP (simulé)."""

    event_id: str = Field(min_length=1, max_length=64)
    type: Literal["payment.succeeded", "payment.failed"]
    intent_id: str = Field(min_length=1, max_length=64)
