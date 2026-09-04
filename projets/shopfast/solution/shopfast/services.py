"""Couche métier. Chaque service reçoit ses dépendances ; aucune ne connaît HTTP."""

from __future__ import annotations

from decimal import Decimal

from shopfast import security  # module (permet le monkeypatch du hachage en test)
from shopfast.config import Settings
from shopfast.errors import (
    AuthError,
    ConflictError,
    EmptyCartError,
    InvalidTransitionError,
    NotFoundError,
    OutOfStockError,
)
from shopfast.models import OrderItemRow, OrderRow, PaymentRow, ProductRow, UserRow
from shopfast.repositories import (
    CartRepository,
    OrderRepository,
    ProductRepository,
    UserRepository,
    WebhookRepository,
)
from shopfast.schemas import CartLine, CartRead
from shopfast.security import create_access_token

_CANCELLABLE = {"pending", "paid"}
_NEXT_STATUS: dict[str, set[str]] = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled", "refunded"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
    "refunded": set(),
}


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    async def register(self, *, email: str, password: str) -> UserRow:
        return await self._users.create(email=email, password_hash=security.hash_password(password))

    async def login(self, *, email: str, password: str) -> str:
        user = await self._users.by_email(email)
        if user is None or not security.verify_password(password, user.password_hash):
            raise AuthError("identifiants invalides")
        return create_access_token(
            subject=str(user.id),
            role=user.role,
            secret=self._settings.jwt_secret.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
            expires_minutes=self._settings.access_token_expire_minutes,
        )


class CatalogService:
    def __init__(self, products: ProductRepository) -> None:
        self._products = products

    async def create_product(
        self, *, sku: str, name: str, price: Decimal, stock: int
    ) -> ProductRow:
        return await self._products.create(sku=sku, name=name, price=price, stock=stock)

    async def list_products(self) -> list[ProductRow]:
        return await self._products.list_active()

    async def get_product(self, product_id: int) -> ProductRow:
        product = await self._products.get(product_id)
        if product is None or not product.active:
            raise NotFoundError(f"produit {product_id}")
        return product

    async def set_price(self, product_id: int, price: Decimal) -> ProductRow:
        await self.get_product(product_id)
        await self._products.set_price(product_id, price)
        return await self.get_product(product_id)


class CartService:
    def __init__(self, carts: CartRepository, products: ProductRepository) -> None:
        self._carts = carts
        self._products = products

    async def add_item(self, user_id: int, *, product_id: int, quantity: int) -> None:
        product = await self._products.get(product_id)
        if product is None or not product.active:
            raise NotFoundError(f"produit {product_id}")
        await self._carts.upsert(user_id, product_id, quantity)

    async def remove_item(self, user_id: int, product_id: int) -> None:
        await self._carts.remove(user_id, product_id)

    async def view(self, user_id: int) -> CartRead:
        lines: list[CartLine] = []
        total = Decimal("0.00")
        for item in await self._carts.items(user_id):
            product = await self._products.get(item.product_id)
            if product is None:
                continue
            line_total = product.price * item.quantity
            total += line_total
            lines.append(
                CartLine(
                    product_id=product.id,
                    name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                    line_total=line_total,
                )
            )
        return CartRead(items=lines, total=total)


class CheckoutService:
    """Crée une commande depuis le panier : fige les prix, réserve le stock, crée un intent.

    Tout se fait dans **une** transaction (le `commit` est piloté par la route). Si une
    réservation de stock échoue, on relâche ce qui a déjà été réservé et on lève.
    """

    def __init__(
        self,
        carts: CartRepository,
        products: ProductRepository,
        orders: OrderRepository,
    ) -> None:
        self._carts = carts
        self._products = products
        self._orders = orders

    async def checkout(self, user_id: int) -> OrderRow:
        cart_items = await self._carts.items(user_id)
        if not cart_items:
            raise EmptyCartError("panier vide")

        order = OrderRow(user_id=user_id, status="pending", total=Decimal("0.00"))
        total = Decimal("0.00")
        # Tout se passe dans une seule transaction : si une réservation échoue, on lève et
        # la route ne committe pas → toutes les réservations déjà faites sont annulées par
        # le rollback. Pas besoin de « défaire » à la main.
        for item in cart_items:
            product = await self._products.get(item.product_id)
            if product is None or not product.active:
                raise NotFoundError(f"produit {item.product_id}")
            if not await self._products.try_reserve_stock(product.id, item.quantity):
                raise OutOfStockError(f"stock insuffisant pour {product.name}")
            # SNAPSHOT : on copie nom + prix courant dans la ligne de commande
            order.items.append(
                OrderItemRow(
                    product_id=product.id,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                )
            )
            total += product.price * item.quantity

        order.total = total
        order.payment = PaymentRow(
            intent_id=f"pi_{user_id}_{_short_token()}",
            status="requires_payment",
            amount=total,
        )
        self._orders.add(order)
        await self._carts.clear(user_id)
        return order


class OrderService:
    def __init__(self, orders: OrderRepository, products: ProductRepository) -> None:
        self._orders = orders
        self._products = products

    async def get(self, order_id: int, user_id: int) -> OrderRow:
        order = await self._orders.get_for_user(order_id, user_id)
        if order is None:
            raise NotFoundError(f"commande {order_id}")
        return order

    async def list(self, user_id: int) -> list[OrderRow]:
        return await self._orders.list_for_user(user_id)

    async def cancel(self, order_id: int, user_id: int) -> OrderRow:
        order = await self.get(order_id, user_id)
        if order.status not in _CANCELLABLE:
            raise InvalidTransitionError(f"une commande '{order.status}' ne s'annule pas")
        # on rend le stock réservé
        for item in order.items:
            await self._products.release_stock(item.product_id, item.quantity)
        order.status = "cancelled"
        if order.payment is not None and order.payment.status == "requires_payment":
            order.payment.status = "failed"
        return order


class WebhookService:
    """Traite les webhooks du PSP. **Idempotent** : rejouer un `event_id` ne fait rien."""

    def __init__(
        self,
        webhooks: WebhookRepository,
        orders: OrderRepository,
        products: ProductRepository,
    ) -> None:
        self._webhooks = webhooks
        self._orders = orders
        self._products = products

    async def handle(self, *, event_id: str, event_type: str, intent_id: str) -> None:
        # 1) idempotence AVANT tout autre écriture : rejeu -> on sort sans rien changer
        if not await self._webhooks.mark_processed(event_id):
            return

        order = await self._orders.by_intent(intent_id)
        if order is None or order.payment is None:
            raise NotFoundError(f"intent {intent_id}")

        if event_type == "payment.succeeded":
            self._apply_succeeded(order)
        elif event_type == "payment.failed":
            await self._apply_failed(order)

    @staticmethod
    def _apply_succeeded(order: OrderRow) -> None:
        if order.payment is None:
            return
        if order.payment.status == "succeeded":  # garde-fou : déjà payé
            return
        if order.status != "pending":
            raise ConflictError(f"commande '{order.status}' : paiement inattendu")
        from datetime import UTC, datetime

        order.payment.status = "succeeded"
        order.status = "paid"
        order.paid_at = datetime.now(UTC)

    async def _apply_failed(self, order: OrderRow) -> None:
        if order.payment is None or order.payment.status == "succeeded":
            return
        order.payment.status = "failed"
        if order.status == "pending":
            order.status = "cancelled"
            for item in order.items:
                await self._products.release_stock(item.product_id, item.quantity)


def _short_token() -> str:
    import secrets

    return secrets.token_hex(6)
