"""Routes HTTP — fines : valider, appeler le service, committer, mapper la sortie."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Response, status

from shopfast.deps import (
    AdminUser,
    AuthServiceDep,
    CartServiceDep,
    CatalogServiceDep,
    CheckoutServiceDep,
    CurrentUser,
    OrderServiceDep,
    SessionDep,
    WebhookServiceDep,
)
from shopfast.schemas import (
    CartItemIn,
    CartRead,
    LoginRequest,
    OrderRead,
    PaymentIntentRead,
    ProductCreate,
    ProductRead,
    RegisterRequest,
    TokenResponse,
    WebhookEvent,
)

router = APIRouter()


# --- auth ---------------------------------------------------------------
@router.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(
    payload: RegisterRequest, service: AuthServiceDep, session: SessionDep
) -> dict[str, object]:
    user = await service.register(email=payload.email, password=payload.password)
    await session.commit()
    return {"id": user.id, "email": user.email}


@router.post("/auth/login", tags=["auth"])
async def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return TokenResponse(
        access_token=await service.login(email=payload.email, password=payload.password)
    )


# --- catalogue (lecture publique, écriture admin) -------------------
@router.get("/products", response_model=list[ProductRead], tags=["catalogue"])
async def list_products(service: CatalogServiceDep) -> list[ProductRead]:
    return [ProductRead.model_validate(p) for p in await service.list_products()]


@router.get("/products/{product_id}", response_model=ProductRead, tags=["catalogue"])
async def get_product(product_id: int, service: CatalogServiceDep) -> ProductRead:
    return ProductRead.model_validate(await service.get_product(product_id))


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    tags=["catalogue"],
)
async def create_product(
    payload: ProductCreate, _admin: AdminUser, service: CatalogServiceDep, session: SessionDep
) -> ProductRead:
    product = await service.create_product(
        sku=payload.sku, name=payload.name, price=payload.price, stock=payload.stock
    )
    await session.commit()
    return ProductRead.model_validate(product)


@router.patch("/products/{product_id}/price", response_model=ProductRead, tags=["catalogue"])
async def set_price(
    product_id: int,
    body: dict[str, Decimal],
    _admin: AdminUser,
    service: CatalogServiceDep,
    session: SessionDep,
) -> ProductRead:
    product = await service.set_price(product_id, Decimal(str(body["price"])))
    await session.commit()
    return ProductRead.model_validate(product)


# --- panier -----------------------------------------------------------
@router.get("/cart", response_model=CartRead, tags=["panier"])
async def view_cart(user: CurrentUser, service: CartServiceDep) -> CartRead:
    return await service.view(user.id)


@router.put("/cart/items", response_model=CartRead, tags=["panier"])
async def put_cart_item(
    payload: CartItemIn, user: CurrentUser, service: CartServiceDep, session: SessionDep
) -> CartRead:
    await service.add_item(user.id, product_id=payload.product_id, quantity=payload.quantity)
    await session.commit()
    return await service.view(user.id)


@router.delete("/cart/items/{product_id}", response_model=CartRead, tags=["panier"])
async def delete_cart_item(
    product_id: int, user: CurrentUser, service: CartServiceDep, session: SessionDep
) -> CartRead:
    await service.remove_item(user.id, product_id)
    await session.commit()
    return await service.view(user.id)


# --- commandes ------------------------------------------------------
@router.post(
    "/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED, tags=["commandes"]
)
async def checkout(
    user: CurrentUser,
    service: CheckoutServiceDep,
    session: SessionDep,
    response: Response,
) -> OrderRead:
    order = await service.checkout(user.id)
    await session.commit()
    response.headers["Location"] = f"/orders/{order.id}"
    return OrderRead.model_validate(order)


@router.get("/orders", response_model=list[OrderRead], tags=["commandes"])
async def list_orders(user: CurrentUser, service: OrderServiceDep) -> list[OrderRead]:
    return [OrderRead.model_validate(o) for o in await service.list(user.id)]


@router.get("/orders/{order_id}", response_model=OrderRead, tags=["commandes"])
async def get_order(order_id: int, user: CurrentUser, service: OrderServiceDep) -> OrderRead:
    return OrderRead.model_validate(await service.get(order_id, user.id))


@router.get("/orders/{order_id}/payment", response_model=PaymentIntentRead, tags=["commandes"])
async def get_payment_intent(
    order_id: int, user: CurrentUser, service: OrderServiceDep
) -> PaymentIntentRead:
    order = await service.get(order_id, user.id)
    assert order.payment is not None
    return PaymentIntentRead(
        intent_id=order.payment.intent_id,
        amount=order.payment.amount,
        status=order.payment.status,
    )


@router.post("/orders/{order_id}/cancel", response_model=OrderRead, tags=["commandes"])
async def cancel_order(
    order_id: int, user: CurrentUser, service: OrderServiceDep, session: SessionDep
) -> OrderRead:
    order = await service.cancel(order_id, user.id)
    await session.commit()
    return OrderRead.model_validate(order)


# --- webhook PSP (pas d'auth utilisateur : signature en prod) ------
@router.post("/payments/webhook", status_code=status.HTTP_200_OK, tags=["paiement"])
async def payment_webhook(
    event: WebhookEvent, service: WebhookServiceDep, session: SessionDep
) -> dict[str, str]:
    await service.handle(event_id=event.event_id, event_type=event.type, intent_id=event.intent_id)
    await session.commit()
    return {"status": "ok"}
