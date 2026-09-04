"""Tests de `shopfast` — la Definition of Done du brief, point par point."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from shopfast.models import ProductRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker


def money(value: object) -> Decimal:
    """Compare des montants sans se soucier des zéros de fin (Decimal('30.0') == '30.00')."""
    return Decimal(str(value))


async def _product(api: httpx.AsyncClient, admin: dict, **over: object) -> dict:
    body = {"sku": "SKU-1", "name": "Clavier", "price": "49.90", "stock": 10}
    body.update(over)
    r = await api.post("/products", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


async def _add_to_cart(api: httpx.AsyncClient, customer: dict, product_id: int, qty: int) -> None:
    r = await api.put(
        "/cart/items", json={"product_id": product_id, "quantity": qty}, headers=customer
    )
    assert r.status_code == 200, r.text


# --- auth & RBAC ----------------------------------------------------
async def test_register_duplicate_email_409(api: httpx.AsyncClient) -> None:
    await api.post("/auth/register", json={"email": "a@b.co", "password": "password-123"})
    r = await api.post("/auth/register", json={"email": "a@b.co", "password": "password-123"})
    assert r.status_code == 409


async def test_login_bad_credentials_401(api: httpx.AsyncClient) -> None:
    await api.post("/auth/register", json={"email": "c@d.co", "password": "password-123"})
    r = await api.post("/auth/login", json={"email": "c@d.co", "password": "wrong"})
    assert r.status_code == 401


async def test_create_product_requires_admin(
    api: httpx.AsyncClient, customer: dict, admin: dict
) -> None:
    assert (
        await api.post("/products", json={"sku": "X", "name": "N", "price": "1.00", "stock": 1})
    ).status_code == 401
    r = await api.post(
        "/products", json={"sku": "X", "name": "N", "price": "1.00", "stock": 1}, headers=customer
    )
    assert r.status_code == 403
    assert (
        await api.post(
            "/products",
            json={"sku": "X", "name": "N", "price": "1.00", "stock": 1},
            headers=admin,
        )
    ).status_code == 201


async def test_duplicate_sku_409(api: httpx.AsyncClient, admin: dict) -> None:
    await _product(api, admin, sku="DUP")
    r = await api.post(
        "/products",
        json={"sku": "DUP", "name": "Autre", "price": "1.00", "stock": 1},
        headers=admin,
    )
    assert r.status_code == 409


# --- panier + checkout -------------------------------------------
async def test_cart_and_checkout_flow(
    api: httpx.AsyncClient,
    customer: dict,
    admin: dict,
    session_factory: async_sessionmaker,
) -> None:
    product = await _product(api, admin, price="10.00", stock=5)
    await _add_to_cart(api, customer, product["id"], 3)

    cart = (await api.get("/cart", headers=customer)).json()
    assert money(cart["total"]) == money("30.00")

    r = await api.post("/orders", json={}, headers=customer)
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "pending"
    assert money(order["total"]) == money("30.00")
    assert money(order["items"][0]["unit_price"]) == money("10.00")
    assert r.headers["location"] == f"/orders/{order['id']}"

    # stock réservé
    async with session_factory() as s:
        stock = (
            await s.scalars(select(ProductRow.stock).where(ProductRow.id == product["id"]))
        ).one()
    assert stock == 2

    # panier vidé
    assert (await api.get("/cart", headers=customer)).json()["items"] == []


async def test_checkout_empty_cart_400(api: httpx.AsyncClient, customer: dict) -> None:
    assert (await api.post("/orders", json={}, headers=customer)).status_code == 400


# --- DoD 1 : pas de survente ------------------------------------
async def test_cannot_order_more_than_stock(
    api: httpx.AsyncClient, customer: dict, other_customer: dict, admin: dict
) -> None:
    product = await _product(api, admin, price="5.00", stock=1)

    await _add_to_cart(api, customer, product["id"], 1)
    await _add_to_cart(api, other_customer, product["id"], 1)

    first = await api.post("/orders", json={}, headers=customer)
    second = await api.post("/orders", json={}, headers=other_customer)

    assert first.status_code == 201
    assert second.status_code == 409  # OutOfStockError
    assert "stock" in second.json()["detail"].lower()


async def test_failed_reservation_rolls_back_earlier_reservations(
    api: httpx.AsyncClient, customer: dict, admin: dict, session_factory: async_sessionmaker
) -> None:
    ok = await _product(api, admin, sku="OK", price="1.00", stock=10)
    ko = await _product(api, admin, sku="KO", price="1.00", stock=1)
    await _add_to_cart(api, customer, ok["id"], 2)
    await _add_to_cart(api, customer, ko["id"], 5)  # impossible

    assert (await api.post("/orders", json={}, headers=customer)).status_code == 409

    async with session_factory() as s:
        stocks = {r.sku: r.stock for r in (await s.scalars(select(ProductRow))).all()}
    assert stocks == {"OK": 10, "KO": 1}  # rien n'a été consommé


# --- DoD 4 : total figé --------------------------------------
async def test_order_total_frozen_when_price_changes(
    api: httpx.AsyncClient, customer: dict, admin: dict
) -> None:
    product = await _product(api, admin, price="20.00", stock=5)
    await _add_to_cart(api, customer, product["id"], 2)
    order = (await api.post("/orders", json={}, headers=customer)).json()
    assert money(order["total"]) == money("40.00")

    # le prix catalogue change APRÈS la commande
    assert (
        await api.patch(f"/products/{product['id']}/price", json={"price": "999.00"}, headers=admin)
    ).status_code == 200

    refetched = (await api.get(f"/orders/{order['id']}", headers=customer)).json()
    assert money(refetched["total"]) == money("40.00")
    assert money(refetched["items"][0]["unit_price"]) == money("20.00")


# --- DoD 3 : isolation des commandes -------------------------
async def test_customer_cannot_read_or_cancel_another_order(
    api: httpx.AsyncClient, customer: dict, other_customer: dict, admin: dict
) -> None:
    product = await _product(api, admin, stock=5)
    await _add_to_cart(api, customer, product["id"], 1)
    order = (await api.post("/orders", json={}, headers=customer)).json()

    assert (await api.get(f"/orders/{order['id']}", headers=other_customer)).status_code == 404
    assert (
        await api.post(f"/orders/{order['id']}/cancel", json={}, headers=other_customer)
    ).status_code == 404


async def test_orders_list_is_scoped_to_user(
    api: httpx.AsyncClient, customer: dict, other_customer: dict, admin: dict
) -> None:
    product = await _product(api, admin, stock=5)
    await _add_to_cart(api, customer, product["id"], 1)
    await api.post("/orders", json={}, headers=customer)

    assert len((await api.get("/orders", headers=customer)).json()) == 1
    assert (await api.get("/orders", headers=other_customer)).json() == []


# --- paiement + DoD 2 : webhook idempotent -----------------
async def _order_with_intent(
    api: httpx.AsyncClient, customer: dict, admin: dict, *, stock: int = 5, qty: int = 1
) -> tuple[dict, str]:
    product = await _product(api, admin, stock=stock)
    await _add_to_cart(api, customer, product["id"], qty)
    order = (await api.post("/orders", json={}, headers=customer)).json()
    intent = (await api.get(f"/orders/{order['id']}/payment", headers=customer)).json()
    return order, intent["intent_id"]


async def test_webhook_marks_order_paid(
    api: httpx.AsyncClient, customer: dict, admin: dict
) -> None:
    order, intent_id = await _order_with_intent(api, customer, admin)
    r = await api.post(
        "/payments/webhook",
        json={"event_id": "evt_1", "type": "payment.succeeded", "intent_id": intent_id},
    )
    assert r.status_code == 200
    got = (await api.get(f"/orders/{order['id']}", headers=customer)).json()
    assert got["status"] == "paid"
    assert got["paid_at"] is not None


async def test_replaying_webhook_does_not_double(
    api: httpx.AsyncClient, customer: dict, admin: dict, session_factory: async_sessionmaker
) -> None:
    order, intent_id = await _order_with_intent(api, customer, admin)
    payload = {"event_id": "evt_same", "type": "payment.succeeded", "intent_id": intent_id}

    r1 = await api.post("/payments/webhook", json=payload)
    r2 = await api.post("/payments/webhook", json=payload)
    r3 = await api.post("/payments/webhook", json=payload)
    assert {r1.status_code, r2.status_code, r3.status_code} == {200}

    got = (await api.get(f"/orders/{order['id']}", headers=customer)).json()
    assert got["status"] == "paid"

    async with session_factory() as s:
        from shopfast.models import OrderRow, PaymentRow

        orders = (await s.scalars(select(OrderRow))).all()
        payments = (await s.scalars(select(PaymentRow))).all()
    assert len(orders) == 1 and len(payments) == 1  # aucun doublon


async def test_webhook_failure_cancels_and_releases_stock(
    api: httpx.AsyncClient, customer: dict, admin: dict, session_factory: async_sessionmaker
) -> None:
    order, intent_id = await _order_with_intent(api, customer, admin, stock=3, qty=2)

    async with session_factory() as s:
        before = (await s.scalars(select(ProductRow.stock))).one()
    assert before == 1  # 3 - 2 réservés

    r = await api.post(
        "/payments/webhook",
        json={"event_id": "evt_ko", "type": "payment.failed", "intent_id": intent_id},
    )
    assert r.status_code == 200

    got = (await api.get(f"/orders/{order['id']}", headers=customer)).json()
    assert got["status"] == "cancelled"
    async with session_factory() as s:
        after = (await s.scalars(select(ProductRow.stock))).one()
    assert after == 3  # stock rendu


async def test_webhook_unknown_intent_404(api: httpx.AsyncClient) -> None:
    r = await api.post(
        "/payments/webhook",
        json={"event_id": "e", "type": "payment.succeeded", "intent_id": "pi_nope"},
    )
    assert r.status_code == 404


# --- annulation --------------------------------------------
async def test_cancel_pending_order_releases_stock(
    api: httpx.AsyncClient, customer: dict, admin: dict, session_factory: async_sessionmaker
) -> None:
    product = await _product(api, admin, stock=5)
    await _add_to_cart(api, customer, product["id"], 2)
    order = (await api.post("/orders", json={}, headers=customer)).json()

    r = await api.post(f"/orders/{order['id']}/cancel", json={}, headers=customer)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    async with session_factory() as s:
        stock = (
            await s.scalars(select(ProductRow.stock).where(ProductRow.id == product["id"]))
        ).one()
    assert stock == 5


async def test_cannot_cancel_paid_then_shipped_order(
    api: httpx.AsyncClient, customer: dict, admin: dict, session_factory: async_sessionmaker
) -> None:
    order, intent_id = await _order_with_intent(api, customer, admin)
    await api.post(
        "/payments/webhook",
        json={"event_id": "evt_p", "type": "payment.succeeded", "intent_id": intent_id},
    )
    # on passe la commande à "shipped" en base (pas d'endpoint dédié dans ce périmètre)
    async with session_factory() as s:
        from shopfast.models import OrderRow

        o = await s.get(OrderRow, order["id"])
        assert o is not None
        o.status = "shipped"
        await s.commit()

    r = await api.post(f"/orders/{order['id']}/cancel", json={}, headers=customer)
    assert r.status_code == 409


async def test_openapi(api: httpx.AsyncClient) -> None:
    paths = (await api.get("/openapi.json")).json()["paths"]
    for p in ("/products", "/cart", "/orders", "/payments/webhook"):
        assert p in paths


@pytest.mark.parametrize("bad", [{"price": "0"}, {"price": "-1"}, {"stock": -5}])
async def test_product_validation(api: httpx.AsyncClient, admin: dict, bad: dict) -> None:
    body = {"sku": "V", "name": "N", "price": "1.00", "stock": 1}
    body.update(bad)
    assert (await api.post("/products", json=body, headers=admin)).status_code == 422
