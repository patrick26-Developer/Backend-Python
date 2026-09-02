# Module 04 — Exercices

> On branche `taskman` sur une vraie base. Objectif : les **tests d'intégration** restent
> verts (adaptés en async), et un test prouve qu'il n'y a **pas de N+1**.

**Prérequis :**

```bash
pip install -e ".[dev]"        # ajoute sqlalchemy, alembic, aiosqlite, asyncpg
# (optionnel) PostgreSQL local :
docker compose up -d db
```

**Filet de sécurité :** `git commit -m "checkpoint: avant module 04"`.

---

## Exercice 04.1 — Le socle DB : `Base`, moteur, session 🟡

1. `taskman/db/base.py` : `class Base(DeclarativeBase)` + un `TypeDecorator` `TZDateTime`
   qui force les `datetime` en UTC *aware* (bind **et** result). + `utcnow()`.
2. `taskman/db/engine.py` :
   - `create_engine(url, *, echo=False) -> AsyncEngine` : `create_async_engine`,
     `pool_pre_ping=True` ; si SQLite en mémoire → `StaticPool` + `check_same_thread=False` ;
     si SQLite → écouteur `connect` qui fait `PRAGMA foreign_keys=ON`.
   - `create_session_factory(engine) -> async_sessionmaker` : `expire_on_commit=False`,
     `autoflush=False`.
3. `taskman/db/session.py` : `async def get_session(request) -> AsyncIterator[AsyncSession]`
   qui lit `request.app.state.session_factory` et `yield` une session dans un `async with`.
4. `taskman/core/config.py` : ajoute `database_url` (défaut
   `sqlite+aiosqlite:///./taskman.db`) et `db_echo: bool = False`.

**Critères d'acceptation**
- [ ] `create_engine("sqlite+aiosqlite://")` renvoie un moteur avec `StaticPool`.
- [ ] Un `datetime` naïf écrit puis relu ressort *aware* (UTC).
- [ ] `mypy` OK sur `taskman/db/`.

---

## Exercice 04.2 — Les modèles ORM 🟡

1. `taskman/db/models.py` :
   - `ProjectRow` : `id`, `name` (`String(200)`), `created_at` (`TZDateTime`, défaut
     `utcnow`), relation `tasks` (`cascade="all, delete-orphan"`, `passive_deletes=True`).
   - `TaskRow` : tous les champs de `TaskRead` **sauf** `is_overdue` (calculé côté Pydantic) ;
     `project_id` FK vers `projects.id` avec `ondelete="CASCADE"` et `index=True` ;
     `status` en `SAEnum(TaskStatus, native_enum=False, length=16)` ;
     `tags` et `checklist` en `JSON` ; `estimate_hours` en `Numeric(5, 2)` ;
     `created_at`/`updated_at` en `TZDateTime` (avec `onupdate=utcnow`) ;
     relation `project`.
   - un index composite `(project_id, status)`.
2. Ajoute `from_attributes=True` au `model_config` de `TaskRead`
   (pour `TaskRead.model_validate(row)`).
3. Crée `taskman/schemas/project.py` : `ProjectCreate`, `ProjectRead` (avec `task_count`),
   `ProjectPage`. Ré-exporte-les depuis `schemas/__init__.py`.

**Critères d'acceptation**
- [ ] `python -c "from taskman.db.models import TaskRow, ProjectRow"` fonctionne.
- [ ] `TaskRead.model_validate(<un TaskRow>)` produit un `TaskRead` correct (checklist incluse).
- [ ] `mypy` OK.

---

## Exercice 04.3 — Le repository SQLAlchemy 🔴

1. `taskman/repositories/base.py` : passe `TaskRepository` en **async** ; ajoute
   `UnitOfWork` (`commit`/`rollback` async) et `ProjectRepository`.
2. `taskman/repositories/memory.py` : passe les impls en `async` (trivial) ; ajoute
   `InMemoryProjectRepository` et `NullUnitOfWork`.
3. `taskman/repositories/sqlalchemy.py` :
   - `SqlAlchemyTaskRepository(session)` : `create` (`add` + `flush` + `refresh`),
     `get` (`session.get`), `list` (filtres `select().where()`, `total` via `func.count` sur
     sous-requête, tri, pagination), `update` (`session.get` + `setattr` des champs
     `exclude_unset` + `flush`), `delete` (`session.get` + `session.delete`).
   - `SqlAlchemyProjectRepository(session)` : `create`, `get` (avec `task_count`), `list`
     (task_count via `outerjoin` + `group_by` — **une seule requête**).
   - un helper `_task_to_read(row) -> TaskRead`.

**Critères d'acceptation**
- [ ] Aucune méthode du repository ne fait `commit()`.
- [ ] `list()` renvoie `(rows, total)` avec le total **avant** pagination.
- [ ] `SqlAlchemyProjectRepository.list()` ne fait **pas** de requête par projet (vérifie
      avec `echo=True`).

---

## Exercice 04.4 — Service transactionnel + injection 🔴

1. `taskman/services/tasks.py` : `TaskService(tasks, uow)` **async**. Les écritures
   (`create`, `update` si trouvé, `delete` si trouvé) appellent `await self._uow.commit()`.
   Les lectures, non.
2. `taskman/services/projects.py` : `ProjectService` idem.
3. `taskman/api/deps.py` :
   - `SessionDep = Annotated[AsyncSession, Depends(get_session)]` ;
   - `get_task_repository(session)` → `SqlAlchemyTaskRepository(session)` ;
   - `get_task_service(repo, session)` → `TaskService(repo, uow=session)` ;
   - idem projets.
4. `taskman/main.py` : `lifespan` crée le moteur (`create_engine(settings.database_url,
   echo=settings.db_echo)`) + `session_factory` dans `app.state`, et `await engine.dispose()`
   à l'arrêt. Monte le router `projects`.

**Critères d'acceptation**
- [ ] Un test avec un faux `UnitOfWork` (`SpyUoW`) prouve : `commit` appelé sur `create`,
      **pas** sur `list`.
- [ ] `get_session` demandé par le repo ET le service → **même** session (cache de
      sous-dépendance).
- [ ] `fastapi dev taskman/main.py` démarre.

---

## Exercice 04.5 — Alembic 🔴

1. `alembic.ini` (sans `sqlalchemy.url`) + `alembic/env.py` **async** qui : lit l'URL depuis
   `get_settings()`, importe `taskman.db.models` (effet de bord), pointe `target_metadata` sur
   `Base.metadata`, utilise `render_as_batch=True` (SQLite) et un `render_item` qui rend
   `TZDateTime` comme `sa.DateTime(timezone=True)`.
2. `alembic revision --autogenerate -m "initial schema"` → **relis** le fichier.
3. `alembic upgrade head` sur une base neuve → les 2 tables existent.
4. `alembic downgrade base` puis `upgrade head` → OK dans les deux sens.

**Critères d'acceptation**
- [ ] `alembic upgrade head` monte une base vide au schéma courant.
- [ ] `alembic downgrade -1` fonctionne.
- [ ] La migration est lisible (pas de `taskman.db.base.TZDateTime` non importé dedans).

---

## Exercice 04.6 — Tests sur base + garde-fou migration 🔴

1. `tests/conftest.py` :
   - `db_engine` (fixture async) : `create_engine("sqlite+aiosqlite://")` + `create_all` ;
   - `session_factory`, `db_session` ;
   - `client` : `create_app(Settings(env="test", database_url=...))`,
     `app.dependency_overrides[get_session] = <session de test>`, `httpx.AsyncClient` +
     `ASGITransport`.
2. Adapte `tests/unit/test_repository.py` : teste `SqlAlchemyTaskRepository` sur `db_session`
   (roundtrip, filtres, pagination, PATCH, delete, `task_count` sans N+1).
3. `tests/unit/test_service.py` : teste `TaskService` avec les repos **en mémoire** + un
   `SpyUoW`.
4. `tests/integration/test_tasks_api.py` : tout en `async def`, via `httpx.AsyncClient`.
   Ajoute : persistance entre 2 requêtes, isolation entre tests, `task_count` via l'API.
5. `tests/integration/test_migrations.py` : `alembic upgrade head` puis `alembic check` →
   aucun changement en attente. Marque `@pytest.mark.slow`.

**Critères d'acceptation**
- [ ] `pytest` 100 % vert et déterministe.
- [ ] Modifier un modèle sans migration → `test_migrations` échoue.
- [ ] Deux tests successifs ne partagent aucune donnée.

---

## Rendu

```
taskman/
├── db/{base,engine,session,models}.py
├── repositories/{base,memory,sqlalchemy}.py
├── services/{tasks,projects}.py
├── api/{deps.py, routes/{meta,projects,tasks}.py}
└── main.py
alembic/ + alembic.ini + docker-compose.yml
```

```bash
alembic upgrade head
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "feat(module-04): SQLAlchemy 2.0 async + Alembic + repository SQL"
```

Puis [`../solutions/README.md`](../solutions/) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

**Mini-projet associé** : [`../../projets/checkpoints/shorturl/`](../../projets/checkpoints/shorturl/BRIEF.md).
