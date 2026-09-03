# Module 07 — Tests

> **Objectif** : transformer les ~85 tests accumulés en une **stratégie**. Pyramide,
> fabriques, base de test isolée, TDD, couverture qui bloque la CI, tests sur un vrai
> PostgreSQL.
>
> **Durée estimée** : 8 à 12 h.
> **Pré-requis** : Modules 03–06.

---

## 1. La testabilité est une propriété d'**architecture**

Si `taskman` est difficile à tester, ce n'est pas un problème de tests — c'est un problème
de conception. Les Modules 03–06 ont rendu le code testable **par construction** :

- les **couches** → on teste le service sans HTTP, le repository sans le service ;
- les **`Protocol`** → on remplace le repository par un faux en 5 lignes ;
- **`Depends`** → `app.dependency_overrides` remplace n'importe quel maillon ;
- **`create_app(settings)`** → une app isolée par test.

Un test difficile à écrire est un **signal** : la responsabilité est mal placée.

---

## 2. La pyramide des tests

```
        /\        e2e          peu nombreux, lents, fragiles, réalistes
       /  \                    (vrai PostgreSQL, tout le stack)
      /----\      intégration  moyens : l'API + la DB (SQLite in-memory)
     /      \                  via httpx.AsyncClient
    /--------\    unitaires    nombreux, rapides, ciblés
   /__________\                (service avec faux repo ; schémas ; sécurité)
```

| Niveau | Ce qu'on teste | Vitesse | Dans `taskman` |
|---|---|---|---|
| **unitaire** | une classe/fonction isolée | µs–ms | `tests/unit/` : `test_service`, `test_models`, `test_auth`, `test_repository` |
| **intégration** | l'API HTTP + la persistance | ms | `tests/integration/` : `httpx.AsyncClient` + SQLite in-memory |
| **e2e** | tout le stack, infra réelle | s | `tests/e2e/` : PostgreSQL via `testcontainers` |

**Règle** : la plupart des tests sont unitaires. On monte d'un niveau **seulement** quand le
niveau inférieur ne peut pas couvrir le risque (une jointure SQL, l'`ILIKE` de PostgreSQL,
le comportement transactionnel).

---

## 3. `pytest` : les briques

### Fixtures

Une fixture = une **dépendance de test** fournie par injection. `scope` contrôle la durée de
vie :

```python
@pytest.fixture              # scope="function" (défaut) : recréée à chaque test
@pytest.fixture(scope="module")   # partagée par le fichier
@pytest.fixture(scope="session")  # une seule fois (ex. le conteneur PostgreSQL)
```

`conftest.py` : les fixtures **partagées** (découvertes automatiquement, sans import).
`taskman` en a : `db_engine`, `session_factory`, `db_session`, `app`, `client`,
`member_client`, `admin_client`.

### Fixtures async

```python
@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
```

`asyncio_mode = "auto"` (dans `pyproject.toml`) : les tests `async def` tournent sans
décorateur ; les **fixtures** async gardent `@pytest_asyncio.fixture`.

### Paramétrage

```python
@pytest.mark.parametrize("payload", [
    {"title": "   "}, {"title": "x", "priority": 6}, {"title": "x", "due_date": PAST},
])
async def test_create_rejects_invalid(member_client, payload):
    assert (await member_client.post("/tasks", json=payload)).status_code == 422
```

Un test, N cas. Chaque cas apparaît séparément dans le rapport.

### Marqueurs

```python
@pytest.mark.slow    # test lent (sous-processus)
@pytest.mark.e2e     # nécessite Docker
```

Déclarés dans `pyproject.toml` (`markers = [...]`), `--strict-markers` refuse les fautes de
frappe. Exécution ciblée : `pytest -m "not slow and not e2e"` (défaut rapide en local).

---

## 4. Tester l'API async : `httpx.AsyncClient` + `ASGITransport`

```python
from httpx import ASGITransport, AsyncClient

async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    resp = await client.get("/tasks")
```

- appelle l'app **directement** (pas de socket réseau) ;
- **dans le même *event loop*** que la base de données async — indispensable
  (`TestClient` synchrone crée sa propre boucle → conflits avec l'async DB).
- `ASGITransport` ne déclenche **pas** le `lifespan` par défaut → on surcharge `get_session`
  pour brancher le moteur de test (le moteur du `lifespan` n'est jamais utilisé).

---

## 5. La base de test

### SQLite in-memory jetable (intégration — rapide)

```python
engine = create_engine("sqlite+aiosqlite://")     # StaticPool : 1 connexion partagée
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)  # schéma direct depuis les modèles
```

Fixture `scope="function"` → **base neuve par test** → isolation totale, zéro `tearDown`.

### Le garde-fou migrations (Module 04)

`Base.metadata.create_all` est rapide mais court-circuite Alembic. Un test séparé
(`test_migrations.py`, marqué `slow`) lance `alembic upgrade head` puis `alembic check` :
si un modèle a changé sans migration → **échec**.

### Vrai PostgreSQL avec `testcontainers` (e2e)

```python
@pytest.fixture(scope="module")
def postgres_url():
    from testcontainers.postgres import PostgresContainer
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()
```

Démarre un conteneur PostgreSQL **jetable**, le détruit à la fin. Attrape ce que SQLite
laisse passer : `ILIKE` réel, types `JSONB`, contraintes strictes, comportement
transactionnel. Marqué `e2e` → ignoré si Docker n'est pas là (`pytest.skip`).

---

## 6. Fabriques (*factories* / *builders*)

Répéter `{"title": "...", "project_id": ..., "priority": ...}` dans 40 tests = 40 endroits
à corriger quand un champ change. On centralise :

```python
# tests/factories.py
def task_payload(**over) -> dict:
    return {"title": f"Tâche {_next()}", "project_id": 1} | over

def make_task_create(**over) -> TaskCreate:
    return TaskCreate(**task_payload(**over))
```

- **valeurs par défaut valides** + **surcharges ponctuelles** (`task_payload(priority=5)`).
- un `_next()` qui incrémente → pas de collision entre tests.
- si `project_id` devient obligatoire partout : **une** ligne à changer.

Pour des cas plus riches : `factory_boy`. Ici, des fonctions suffisent.

---

## 7. *Fakes* vs *mocks* vs `dependency_overrides`

| Technique | Quand |
|---|---|
| **fake** (impl. simple, en mémoire) | `InMemoryTaskRepository`, `FakeTaskRepository` du `test_service` — comportement réel, rapide |
| **`app.dependency_overrides[dep] = ...`** | remplacer un maillon dans un test d'API (le repo, la session, la config) |
| **mock** (`unittest.mock`) | vérifier qu'un appel externe a eu lieu (envoi d'e-mail, webhook — Module 08) ; sinon, préfère un *fake* |
| **`monkeypatch`** | remplacer une fonction module-level (le hachage argon2 → trivial en test) |

`taskman` privilégie les **fakes** : un `FakeTaskRepository` qui *fonctionne* teste mieux
qu'un mock qui *simule*.

---

## 8. Couverture (*coverage*)

```toml
[tool.coverage.report]
fail_under = 85          # la CI échoue en-dessous
show_missing = true      # affiche les lignes non couvertes
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "\\.\\.\\.$"]
```

```bash
pytest --cov=taskman --cov-report=term-missing
```

- **branch coverage** (`branch = true`) : pas seulement « la ligne est exécutée » mais
  « les deux branches du `if` le sont ».
- **la couverture n'est pas un objectif, c'est un révélateur** : 100 % de lignes avec zéro
  assertion utile ne prouve rien. Vise à **couvrir les branches d'erreur** (le `raise`, le
  `return None`, le `except`).
- `fail_under` empêche la régression silencieuse.

---

## 9. TDD — Rouge → Vert → Refactor

Le cycle, appliqué à l'action `POST /tasks/{id}/complete` de ce module :

1. **Rouge** — écris le test *d'abord*, il échoue (la route n'existe pas → 404/405) :
   ```python
   async def test_complete_sets_status_and_timestamp(member_client):
       tid = ...  # une tâche todo
       resp = await member_client.post(f"/tasks/{tid}/complete")
       assert resp.json()["status"] == "done"
       assert resp.json()["completed_at"] is not None
   ```
2. **Vert** — le code **minimal** pour passer : colonne `completed_at`, `repo.mark_completed`,
   `service.complete`, route. Pas plus.
3. **Refactor** — nettoie (nommage, duplication) en gardant le vert.
4. Ajoute le test suivant (`test_complete_missing_task_is_404`, `..._requires_auth`,
   `..._another_users_task`) et recommence.

L'historique git montre : **les tests commités avant l'implémentation**. C'est vérifiable.

Bénéfices : tu ne codes **que** ce qui est testé ; l'API est conçue du point de vue de
l'appelant ; tu as un filet dès la 1ʳᵉ ligne.

---

## 10. Anatomie de `tests/`

```
tests/
├── __init__.py
├── conftest.py            # fixtures partagées (db, app, clients authentifiés)
├── factories.py           # task_payload(), make_task_create(), make_user_read()
├── unit/
│   ├── test_models.py     # schémas Pydantic (validation, is_overdue)
│   ├── test_repository.py # SqlAlchemyTaskRepository sur SQLite
│   ├── test_service.py    # TaskService avec faux repos (isolation, commits)
│   ├── test_auth.py       # security (hash, JWT) + AuthService
│   └── test_errors_logging.py
├── integration/
│   ├── test_tasks_api.py       # CRUD via httpx
│   ├── test_auth_api.py        # register/login/refresh/RBAC/BOLA
│   ├── test_complete_action.py # l'action `complete` (TDD)
│   └── test_migrations.py      # @slow : alembic check
└── e2e/
    └── test_postgres.py        # @e2e : vrai PostgreSQL via testcontainers
```

---

## 11. Pièges fréquents

1. **`TestClient` synchrone + DB async** → conflits d'*event loop*, tests instables.
2. **Fixture `scope="session"` mutable** partagée → un test pollue le suivant.
3. **Oublier `app.dependency_overrides.clear()`** au *teardown*.
4. **Tester l'implémentation, pas le comportement** (`assert repo.update.called` au lieu de
   `assert response.json()["status"] == "done"`).
5. **Un seul `assert` par test à tout prix** : plusieurs assertions sur *le même* comportement
   sont OK ; un test qui vérifie 5 comportements différents ne l'est pas.
6. **Tests non déterministes** : dépendre de l'ordre, de l'heure système, d'un `sleep`, du
   réseau. Un test *flaky* qu'on relance « pour voir » est un test mort.
7. **Fétichiser la couverture** : 95 % sans assertions sur les cas d'erreur < 80 % qui les
   couvrent.
8. **Recréer la DB via `create_all` et ne jamais tester les migrations.**
9. **Fixtures trop larges** : `admin_client` quand `client` suffit → lenteur (auth, hash).
10. **Ne pas isoler les données** : deux tests qui écrivent dans la même base sans *rollback*.

---

## 12. Ce que `taskman` gagne

- `pyproject.toml` : `pythonpath`, `fail_under = 85`, marqueurs `slow` / `e2e`, `pytest-cov` ;
- `tests/factories.py` (builders) ; `tests/__init__.py` (package) ;
- `tests/e2e/test_postgres.py` (`testcontainers`, vrai PostgreSQL) ;
- l'action `POST /tasks/{id}/complete` + `completed_at`, **développée en TDD** (visible dans git) ;
- couverture mesurée (~87 %), branches d'erreur couvertes.

---

## 13. À savoir refaire sans aide

- Situer un test dans la pyramide et choisir le bon niveau.
- Écrire une fixture (sync et async), choisir son `scope`.
- Tester une API async avec `httpx.AsyncClient` + `ASGITransport`.
- Isoler une base de test (SQLite jetable) et savoir quand passer à `testcontainers`.
- Écrire un *fake* qui satisfait un `Protocol`, surcharger une dépendance.
- Développer une petite fonctionnalité en TDD strict.
- Lire un rapport de couverture et cibler les branches manquantes.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
