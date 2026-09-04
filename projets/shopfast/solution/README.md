# `shopfast` — solution de référence

Projet de domaine : **e-commerce**. Cette solution couvre le **cœur difficile** du domaine
(celui que le brief met en avant), pas tout le périmètre fonctionnel — voir
[`SOLUTION.md`](SOLUTION.md) pour ce qui est dans le périmètre et ce qui ne l'est pas.

## Installation autonome (sans cloner tout le dépôt)

Copie ce dossier (`shopfast/`, `tests/`, `pyproject.toml`), puis :

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install "fastapi[standard]" pydantic-settings "sqlalchemy[asyncio]" aiosqlite \
            "pwdlib[argon2]" pyjwt pytest pytest-asyncio pytest-cov mypy ruff

uvicorn shopfast.main:app --reload   # http://127.0.0.1:8000/docs
pytest -q                            # 21 tests + couverture (échoue si < 85 %) — 91 % obtenu
mypy shopfast                        # --strict, 0 erreur
```

Si tu es déjà dans le dépôt complet (le venv racine a tout), lance directement
`python -m uvicorn ...`, `python -m pytest`, `python -m mypy shopfast` depuis ce dossier.

Config **12-factor**, préfixe `SHOPFAST_` (`SHOPFAST_DATABASE_URL`, `SHOPFAST_JWT_SECRET`…).

## Ce qui est démontré (Definition of Done du brief)

| DoD | Où | Test |
|---|---|---|
| Pas de survente, même sous charge | `ProductRepository.try_reserve_stock` (UPDATE conditionnel atomique) | `test_cannot_order_more_than_stock` |
| Rejouer un webhook de paiement ne double pas | `WebhookRepository.mark_processed` (`event_id` unique) + garde d'état | `test_replaying_webhook_does_not_double` |
| Un client ne lit/n'annule pas la commande d'un autre | `OrderRepository.get_for_user` (filtre `user_id` dans la requête → 404) | `test_customer_cannot_read_or_cancel_another_order` |
| Le total d'une commande ne bouge pas si le prix catalogue change | `OrderItemRow.unit_price` = snapshot à la création | `test_order_total_frozen_when_price_changes` |
| `ruff` + `mypy --strict` + `pytest` verts, couverture > 85 % | — | CI locale |

## Arborescence

```
shopfast/
  config.py       Settings (env only)
  db.py           moteur async, TZDateTime, get_session
  models.py       users / products / cart_items / orders / order_items / payments / processed_webhooks
  security.py     argon2id (params OWASP) + JWT ; monkeypatchable en test
  schemas.py      contrats d'API
  errors.py       hiérarchie ShopError -> codes HTTP
  repositories.py SQL ; try_reserve_stock est LE point sensible
  services.py     auth / catalog / cart / checkout / order / webhook — aucune ne connaît HTTP
  deps.py         DI + get_current_user + require_admin
  routes.py       routes fines
  main.py         create_app + lifespan + handlers d'erreurs (Problem Details)
tests/            httpx async ; fixtures customer / other_customer / admin
```

Énoncé par phases : [`../BRIEF.md`](../BRIEF.md).
