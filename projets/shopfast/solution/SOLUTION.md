# `shopfast` — les choix de conception

## 1. Le total est **figé** à la commande (snapshot)

`OrderItemRow` copie `product_name` **et** `unit_price` au moment du checkout :

```python
order.items.append(OrderItemRow(
    product_id=product.id,
    product_name=product.name,     # snapshot
    unit_price=product.price,      # snapshot — ne bouge JAMAIS
    quantity=item.quantity,
))
order.total = sum(line.unit_price * line.quantity for line in order.items)
```

`GET /orders/{id}` ne recalcule **rien** : il relit `order.total` et `order.items[*].unit_price`.
Si l'admin change le prix catalogue après coup (`PATCH /products/{id}/price`), la commande
passée est inchangée — testé par `test_order_total_frozen_when_price_changes`.

Recalculer le total depuis le catalogue courant serait un bug classique et coûteux (litiges,
comptabilité fausse).

## 2. Stock : décrément **atomique conditionnel**, jamais « lire puis écrire »

```python
UPDATE products SET stock = stock - :qty WHERE id = :id AND stock >= :qty
```

`try_reserve_stock` renvoie `rowcount == 1`. Deux clients achètent le dernier article :
les deux `UPDATE` partent, **un seul** touche une ligne (`stock >= qty` est faux pour le
seul), l'autre lève `OutOfStockError` → 409.

- Un `SELECT stock` puis `UPDATE` aurait une fenêtre de course (les deux lisent « 1 dispo »).
- Sur SQLite (tests) la concurrence est sérialisée, mais **le chemin de code est identique** ;
  sur PostgreSQL c'est une vraie course et le résultat est le même. Le vrai test concurrent
  (`asyncio.gather` sur un pool Postgres) se ferait en e2e, hors suite unitaire.

Si le checkout échoue sur le 2ᵉ article après avoir réservé le 1er : on **ne défait rien à la
main**. Tout se passe dans une transaction ; la route ne committe pas → le rollback annule
toutes les réservations. Testé par `test_failed_reservation_rolls_back_earlier_reservations`.

## 3. Webhook de paiement **idempotent**

Le PSP peut envoyer le même événement deux fois. Deux garde-fous :

1. **`processed_webhooks(event_id PK)`** : `mark_processed` insère la ligne ; `IntegrityError`
   → c'est un rejeu → on sort **sans rien faire**. C'est la **première** chose que fait le
   handler, avant toute autre écriture.
2. **Garde d'état** : `_apply_succeeded` ne fait rien si `payment.status == "succeeded"` déjà,
   et refuse si la commande n'est plus `pending`.

`test_replaying_webhook_does_not_double` envoie 3× le même événement et vérifie : 1 commande,
1 paiement, statut `paid`.

`payment.failed` → commande `cancelled` + **stock rendu** (`release_stock`).

## 4. Isolation des commandes (BOLA / OWASP API #1)

```python
async def get_for_user(self, order_id: int, user_id: int) -> OrderRow | None:
    return ... where(OrderRow.id == order_id, OrderRow.user_id == user_id) ...
```

Le filtre `user_id` est **dans la requête SQL**, pas un `if` après coup. Commande d'un autre
→ `None` → **404** (pas 403 : un 403 confirmerait que la commande existe). `GET /orders`
liste `list_for_user` uniquement. Testé des deux côtés.

## 5. Architecture en couches + transaction pilotée par la route

`route → service → repository → session`. Le **service ne committe jamais** : il fait son
travail (flush inclus si besoin), la **route** appelle `session.commit()` une seule fois à la
fin. Une exception qui remonte → pas de commit → `async with` fait le rollback. On n'a jamais
d'état à moitié écrit (commande sans lignes, stock décrémenté sans commande…).

## 6. Erreurs métier → hiérarchie → code HTTP

`ShopError` → `NotFoundError` (404), `ForbiddenError` (403), `AuthError` (401),
`ConflictError` (409, parent de `OutOfStockError` et `InvalidTransitionError`), fallback 400.
Un seul `exception_handler(ShopError)` mappe via `isinstance`. Le service lève des exceptions
nommées, jamais `HTTPException`.

## 7. `security.py` monkeypatchable

argon2id « OWASP » (`time_cost=2, memory_cost=19_456`) ≈ 150 ms/hash — trop pour une suite.
`services.py` fait `from shopfast import security` (référence **module**) et appelle
`security.hash_password(...)`, ce qui permet à `conftest.py` de le remplacer par un hachage
trivial. (`from shopfast.security import hash_password` figerait le nom à l'import.)

## Périmètre : ce qui n'est PAS dans cette solution

Le brief décrit une cible large ; cette référence se concentre sur les **invariants durs**.
Sont documentés mais non implémentés (extensions naturelles, même patrons) :

- **variantes** produit (taille/couleur) : une table `variants`, le stock passe sur la variante ;
- **panier anonyme** (token) : `cart_items.session_token` au lieu de `user_id` ;
- **back-office** analytique (ventes/jour) : des `GET /admin/*` avec agrégats SQL ;
- **e-mails / notifications** : un worker `taskiq` (patron dans `taskman` Module 08) ;
- **expiration des commandes `pending`** : une tâche périodique qui annule et rend le stock
  après `order_ttl_minutes` (le champ existe déjà dans `Settings`) ;
- **Alembic** : le schéma est créé au démarrage ; en prod → migrations (patron : `shorturl`) ;
- **remboursements** partiels, `shipped`/`delivered` pilotés par le transporteur.

## L'examen

Reprends le brief phase par phase et implémente une extension ci-dessus **sans casser** les
5 invariants (les tests existants doivent rester verts).
