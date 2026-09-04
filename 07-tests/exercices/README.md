# Module 07 — Exercices

> On structure la suite de tests et on développe une fonctionnalité **en TDD**.

**Filet :** `git commit -m "checkpoint: avant module 07"`.

---

## Exercice 07.1 — Structure & configuration 🟢

1. `pyproject.toml` :
   - `[tool.pytest.ini_options]` : `pythonpath = ["."]`, marqueurs `slow` et `e2e`.
   - `[tool.coverage.report]` : `fail_under = 85`, `show_missing = true`,
     `exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "\\.\\.\\.$"]`.
   - `[tool.coverage.run]` : `branch = true`.
   - ajoute `testcontainers[postgres]` aux dépendances `dev`.
2. Crée `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`,
   `tests/e2e/__init__.py`.
3. Vérifie : `pytest --cov=taskman --cov-report=term-missing` affiche la couverture ; elle
   est ≥ 85 %.

**Critères d'acceptation**
- [ ] `pytest -m "not slow and not e2e"` tourne vite (< quelques secondes hors argon2).
- [ ] `--strict-markers` : un marqueur mal orthographié fait échouer.
- [ ] La couverture globale est ≥ 85 %.

---

## Exercice 07.2 — Fabriques 🟢

1. `tests/factories.py` : `task_payload(**over) -> dict`, `make_task_create(**over) ->
   TaskCreate`, `make_user_read(*, role) -> UserRead`, `future(days) -> str`. Un compteur
   `_next()` évite les collisions.
2. Refactore **au moins 3** tests existants pour utiliser les fabriques.

**Critères d'acceptation**
- [ ] `from tests.factories import task_payload` fonctionne.
- [ ] Les tests refactorés passent toujours.
- [ ] Un champ nouvellement obligatoire ne demande **qu'une** modification (dans `factories.py`).

---

## Exercice 07.3 — L'action `complete` en **TDD strict** 🔴

> Écris les tests **avant** le code. Commit les tests (rouge), puis le code (vert).

1. **Rouge** — `tests/integration/test_complete_action.py` :
   - `test_complete_sets_status_and_timestamp` : `POST /tasks/{id}/complete` → `status ==
     "done"`, `completed_at` non nul.
   - `test_complete_is_persisted` : un `GET` ultérieur confirme.
   - `test_complete_missing_task_is_404` (`code == "task_not_found"`).
   - `test_complete_requires_auth` (401).
   - `test_cannot_complete_another_users_task` (404).
   Lance `pytest tests/integration/test_complete_action.py` → **tout rouge**. Commit.
2. **Vert** — le minimum :
   - `TaskRow.completed_at: Mapped[datetime | None]` + `TaskRead.completed_at` ;
   - `TaskRepository.mark_completed(task_id) -> TaskRead | None` (+ impls SQL et mémoire) ;
   - `TaskService.complete(task_id)` : `_assert_can_access` → `mark_completed` → `commit` ;
   - route `POST /tasks/{task_id}/complete` ;
   - `alembic revision --autogenerate -m "task completed_at"` → relire → `upgrade`.
   Lance les tests → **vert**. Commit.
3. **Refactor** — nettoie si besoin, tests toujours verts.

**Critères d'acceptation**
- [ ] L'historique git montre les tests commités **avant** l'implémentation.
- [ ] `mark_completed` est dans le repository (pas de SQL dans le service).
- [ ] `test_migrations` (slow) toujours vert.

---

## Exercice 07.4 — Tests unitaires du service (isolation) 🟡

1. `tests/unit/test_service.py` : avec `InMemoryTaskRepository` + `NullUnitOfWork` ou un
   `SpyUoW`, prouve :
   - deux acteurs différents ne voient que **leurs** tâches ;
   - un `admin` voit **tout** ;
   - accéder à la tâche d'un autre → `TaskNotFoundError` ;
   - `commit()` est appelé sur les écritures, **pas** sur les lectures ;
   - `complete()` appelle `commit()`.

**Critères d'acceptation**
- [ ] Aucun `TestClient` / `httpx` dans ce fichier.
- [ ] Le `SpyUoW` compte les `commit()`.
- [ ] Couverture de `services/tasks.py` ≥ 90 %.

---

## Exercice 07.5 — Tests e2e sur PostgreSQL 🔴

1. `tests/e2e/test_postgres.py` :
   - fixture `postgres_url` (`scope="module"`) via `testcontainers` ; `pytest.skip` si Docker
     est absent.
   - fixture `pg_client` : moteur sur le conteneur, `create_all`, `httpx.AsyncClient`
     authentifié.
   - `test_full_flow_on_real_postgres` : recherche `ILIKE` (casse), `complete`, FK violée → 404.
   - `test_transaction_rollback_on_error` : un payload invalide ne laisse **rien** en base.
2. Marque le fichier `pytestmark = pytest.mark.e2e`.

**Critères d'acceptation**
- [ ] `pytest -m e2e` passe **si** Docker tourne, **skip** sinon (jamais d'échec pour
      « Docker absent »).
- [ ] `pytest -m "not e2e"` ne démarre aucun conteneur.

---

## Exercice 07.6 — Cibler les branches manquantes 🟡

1. `pytest --cov=taskman --cov-report=term-missing` : repère les lignes `Missing`.
2. Pour **3** branches d'erreur non couvertes (un `raise`, un `except`, un `return None`),
   ajoute un test qui les déclenche.
3. Vérifie que la couverture globale monte.

**Critères d'acceptation**
- [ ] 3 branches d'erreur nouvellement couvertes.
- [ ] `ruff` + `mypy` toujours OK.

---

## Rendu

```bash
ruff check . && ruff format --check . && mypy taskman && pytest -m "not e2e"
git add -A && git commit -m "feat(module-07): stratégie de tests — pyramide, factories, testcontainers, action complete en TDD"
```

Puis [`../solutions/README.md`](../solutions/README.md) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

**Mini-projet associé** : [`pollup`](../../projets/checkpoints/pollup/BRIEF.md) — à construire
**entièrement** en TDD.
