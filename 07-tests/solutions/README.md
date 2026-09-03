# Module 07 — Solutions

> Pour ce module, la **solution est la suite de tests elle-même** : [`tests/`](tests/) (copie
> figée de l'état `taskman` v0.7.0). Explication : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
# depuis la racine du dépôt (utilise le vrai taskman + la config pyproject) :
pytest -m "not e2e"                       # rapide
pytest -m e2e                             # nécessite Docker
pytest --cov=taskman --cov-report=term-missing
```

---

## Ce que contient la solution

| Fichier | Rôle | Point clé |
|---|---|---|
| `tests/conftest.py` | fixtures partagées | `app`, `client` (non auth), `member_client`, `admin_client` ; faux hachage argon2 (autouse) |
| `tests/factories.py` | *builders* | `task_payload()`, `make_task_create()` — un seul endroit à corriger |
| `tests/unit/` | tests unitaires | service avec faux repo ; schémas ; sécurité — **aucun HTTP** |
| `tests/integration/` | tests d'API | `httpx.AsyncClient` + SQLite in-memory |
| `tests/integration/test_complete_action.py` | l'action `complete` | **écrite en TDD** (rouge avant vert) |
| `tests/integration/test_migrations.py` | `@slow` | `alembic upgrade` + `alembic check` |
| `tests/e2e/test_postgres.py` | `@e2e` | vrai PostgreSQL via `testcontainers`, *skip* si pas de Docker |

---

## Décisions

### 1. `httpx.AsyncClient` + `ASGITransport`, pas `TestClient`

`TestClient` (synchrone) crée sa propre boucle d'événements → conflits avec la base async.
`AsyncClient` + `ASGITransport` appelle l'app **dans le même *event loop*** que la DB, sans
socket réseau.

### 2. Base neuve par test (`scope="function"`)

SQLite in-memory + `StaticPool`, `create_all` dans la fixture. Isolation **structurelle** :
rien à nettoyer, aucun test ne peut polluer un autre.

### 3. Le garde-fou migrations est **séparé** (`@slow`)

Les tests d'intégration utilisent `create_all` (rapide). **Un** test dédié lance
`alembic upgrade head` + `alembic check` → si un modèle change sans migration, échec. On
paie la lenteur d'Alembic **une** fois.

### 4. e2e : *skip*, jamais *fail*, si Docker est absent

`pytest.importorskip` + `try/except → pytest.skip`. Un développeur sans Docker lance
`pytest -m "not e2e"` et a une suite verte. La CI, elle, a Docker et lance tout.

### 5. Faux hachage en test (fixture autouse)

argon2 « vrai » = ~150 ms/hash × ~30 comptes = plusieurs secondes perdues. On échange
`hash_password`/`verify_password` pour des fonctions triviales — **le comportement testé**
(égalité, rejet) est identique. `tests/unit/test_auth.py` garde le vrai argon2 (il teste la
crypto).

### 6. `fail_under = 85` + `branch = true`

La CI **échoue** sous 85 %. Couverture de **branches** (chaque `if` compte double). Le but
n'est pas le chiffre : c'est de forcer à couvrir les `raise`, `except`, `return None`.

### 7. TDD prouvé par git

`test_complete_action.py` a été commité **avant** l'implémentation (`git log` le montre :
un commit `test(...)` rouge, puis un commit `feat(...)` vert).

---

## Grille d'auto-évaluation

- [ ] Peux-tu tester `TaskService` **sans** lancer d'app FastAPI ?
- [ ] Tes tests d'intégration utilisent-ils une base **neuve** à chaque test ?
- [ ] `pytest -m "not e2e"` est-il rapide ? `pytest -m e2e` *skip*-e-t-il proprement sans Docker ?
- [ ] Ta couverture est-elle ≥ 85 %, **branches comprises** ?
- [ ] Tes tests d'erreur (`404`, `409`, `422`, `401`, `403`) sont-ils tous là ?
- [ ] L'historique git montre-t-il des tests **avant** l'implémentation pour `complete` ?

➡️ [Module 08 — Async avancé & performance](../../08-async-avance-performance/THEORIE.md)
