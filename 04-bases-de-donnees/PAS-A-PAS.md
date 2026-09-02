# Module 04 — Explication pas à pas du code

> On parcourt **chaque fichier nouveau ou modifié**. Ordre de lecture :
> `config → db/base → db/models → db/engine → db/session → repositories → services →
> api/deps → routes → main → alembic → tests`. Garde
> [`solutions/taskman/`](solutions/taskman/) ouvert.

---

## 1. `taskman/core/config.py` (ajouts)

```python
    database_url: str = "sqlite+aiosqlite:///./taskman.db"
    db_echo: bool = False
```

- `database_url` : l'URL SQLAlchemy. Le **driver** est dans l'URL :
  `sqlite+aiosqlite` (dev), `postgresql+asyncpg` (prod).
- `db_echo` : `True` → SQLAlchemy journalise chaque requête SQL. L'outil pour traquer un N+1.
- alimentés par `APP_DATABASE_URL` / `APP_DB_ECHO` (préfixe `APP_`).

---

## 2. `taskman/db/base.py`

```python
class Base(DeclarativeBase):
    """Base commune à tous les modèles ORM."""
```

`DeclarativeBase` (SQLAlchemy 2.0) : toutes les classes de table en héritent. `Base.metadata`
contient la description de **toutes** les tables — c'est ce qu'Alembic compare à la base
réelle.

```python
class TZDateTime(types.TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):   # Python -> base
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect): # base -> Python
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value
```

- `TypeDecorator` : « enrobe » un type existant (`DateTime(timezone=True)`) pour ajouter du
  comportement.
- `process_bind_param` : appelé **avant d'écrire** en base. Un `datetime` sans fuseau → on
  suppose UTC.
- `process_result_value` : appelé **après lecture**. SQLite renvoie du naïf → on rétablit UTC.
- `cache_ok = True` : dit à SQLAlchemy que ce type peut être mis en cache de compilation
  (obligatoire, sinon warning).
- **Pourquoi** : `is_overdue` (côté Pydantic) compare `due_date < datetime.now(UTC)`.
  Comparer un naïf et un *aware* → `TypeError`. Ce type garantit qu'on n'a jamais de naïf.

```python
def utcnow() -> datetime:
    return datetime.now(UTC)
```

Utilisé comme `default=utcnow` sur les colonnes de date.

---

## 3. `taskman/db/models.py`

```python
class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    tasks: Mapped[list[TaskRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True,
    )
```

- `__tablename__` : le nom de la table SQL.
- `Mapped[int]` + `mapped_column(primary_key=True)` : colonne `id`, clé primaire,
  auto-incrémentée.
- `Mapped[str]` (non optionnel) → `NOT NULL`. `String(200)` → `VARCHAR(200)`.
- `default=utcnow` : valeur par défaut **côté Python** (SQLAlchemy appelle `utcnow()` à
  l'insertion).
- `relationship(...)` : le lien objet → objets. `tasks` sera une `list[TaskRow]`.
  - `back_populates="project"` : l'autre bout du lien (dans `TaskRow`). Les deux se tiennent
    à jour mutuellement.
  - `cascade="all, delete-orphan"` : si tu fais `project.tasks.remove(t)`, `t` est supprimée.
  - `passive_deletes=True` : pour un `DELETE` du projet, fais confiance au `ON DELETE CASCADE`
    de la base — ne charge pas les tâches pour les supprimer une par une.

```python
class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project_status", "project_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
```

- `__table_args__` : un **index composite** `(project_id, status)` — pour accélérer
  « les tâches `done` du projet 5 ».
- `ForeignKey("projects.id", ondelete="CASCADE")` : contrainte d'intégrité + suppression en
  cascade **côté base**. `index=True` : un index sur `project_id` (les FK ne sont pas
  indexées automatiquement).

```python
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=16), default=TaskStatus.todo, index=True
    )
```

- `SAEnum(TaskStatus, native_enum=False)` : l'enum est stocké en **`VARCHAR`**, pas en type
  ENUM natif PostgreSQL. Avantages : portable SQLite, et pas de migration spéciale pour
  ajouter une valeur d'enum.

```python
    due_date: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    estimate_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    project: Mapped[ProjectRow] = relationship(back_populates="tasks")
```

- `Mapped[str | None]` → colonne nullable.
- `tags` / `checklist` en `JSON` : stockés comme du JSON dans une colonne. `default=list` :
  liste vide par défaut. **Limite** : pas de requête efficace « où checklist[2].done ».
- `Numeric(5, 2)` : `DECIMAL(5,2)` — exact, pour `estimate_hours`.
- `onupdate=utcnow` : `updated_at` est réécrit à **chaque `UPDATE`** de la ligne.
- `project` : la relation inverse de `ProjectRow.tasks`.

---

## 4. `taskman/db/engine.py`

```python
def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    kwargs = {"echo": echo, "pool_pre_ping": True}
    if _is_memory_sqlite(database_url):
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_async_engine(database_url, **kwargs)
```

- `create_async_engine` : le moteur **async** (utilise `asyncpg` ou `aiosqlite` selon l'URL).
- `pool_pre_ping=True` : avant de réutiliser une connexion du pool, un petit `SELECT 1` — si
  la connexion est morte (timeout réseau, redémarrage DB), on en prend une neuve.
- **SQLite en mémoire** : `StaticPool` force **une seule** connexion pour tout le moteur.
  Sinon, chaque nouvelle connexion ouvre une base `:memory:` **différente** (vide). Réservé
  aux tests.
- `check_same_thread=False` : SQLite interdit par défaut d'utiliser une connexion depuis un
  autre thread ; l'async en a besoin.

```python
    if _is_sqlite(database_url):
        @event.listens_for(engine.sync_engine, "connect")
        def _fk_pragma(dbapi_conn, _rec):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
```

**SQLite n'applique PAS les clés étrangères par défaut.** Cet écouteur exécute
`PRAGMA foreign_keys=ON` sur **chaque** connexion ouverte. Sans ça,
`project_id=999` (projet inexistant) serait accepté.

```python
def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
```

- `async_sessionmaker` : la **fabrique** — `factory()` crée une nouvelle `AsyncSession`.
- `expire_on_commit=False` : après `commit()`, les objets restent lisibles sans re-requête
  (sinon, lire `task.title` après commit → `SELECT` → échoue hors session).
- `autoflush=False` : on décide quand `flush()` (plus prévisible que le flush automatique
  avant chaque `SELECT`).

---

## 5. `taskman/db/session.py`

```python
async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
```

- dépendance FastAPI **avec `yield`** (générateur async).
- `request.app.state.session_factory` : la fabrique rangée au démarrage (voir `main.py`).
- `async with factory() as session` : ouvre une session, **la ferme à la sortie du bloc**
  (fin de requête), y compris si une exception passe → dans ce cas, rien n'a été committé,
  donc la transaction est abandonnée.
- **une session par requête** : le contexte est nouveau à chaque appel de `get_session`.

---

## 6. `taskman/repositories/base.py` (async + UoW)

```python
class UnitOfWork(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

Une **abstraction de transaction**. `AsyncSession` a bien `async def commit()` et
`async def rollback()` → elle *satisfait* ce `Protocol` sans le savoir. Le service dépendra
de `UnitOfWork`, donc **ne connaîtra pas** `AsyncSession` (ni SQLAlchemy).

```python
class TaskRepository(Protocol):
    async def create(self, data: TaskCreate) -> TaskRead: ...
    ...
```

Mêmes méthodes qu'au Module 03, mais **`async`**. C'est la seule modification de
l'interface — et pourtant tout le reste (service, routes) doit suivre. D'où l'intérêt
d'avoir une interface : le changement est **localisé et visible**.

---

## 7. `taskman/repositories/sqlalchemy.py`

```python
def _task_to_read(row: TaskRow) -> TaskRead:
    return TaskRead.model_validate(row)
```

La **traduction ORM → schéma**. Possible grâce à `from_attributes=True` dans
`TaskRead.model_config` : Pydantic lit les attributs de l'objet (`row.title`, `row.tags`…).
`row.checklist` est une `list[dict]` → validée en `list[ChecklistItem]`. On ne renvoie
**jamais** `row` directement au-delà du repository.

```python
class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

Reçoit **la** session (celle de la requête). N'en ouvre ni n'en ferme.

```python
    async def create(self, data: TaskCreate) -> TaskRead:
        row = TaskRow(project_id=data.project_id, title=data.title, ...,
                      tags=list(data.tags),
                      checklist=[item.model_dump() for item in data.checklist])
        self._session.add(row)
        await self._session.flush()     # -> attribue row.id, exécute l'INSERT (sans commit)
        await self._session.refresh(row)  # -> recharge les valeurs par défaut de la base
        return _task_to_read(row)
```

- `checklist=[item.model_dump() for item in data.checklist]` : on stocke des `dict` dans la
  colonne JSON (les `ChecklistItem` ne sont pas sérialisables tels quels).
- `add()` : marque la ligne pour insertion.
- `flush()` : envoie l'`INSERT` **dans la transaction** → `row.id` est renseigné. **Pas** de
  commit (c'est le service).
- `refresh(row)` : relit la ligne (récupère `created_at` généré par `default=utcnow`, etc.).

```python
    async def get(self, task_id: int) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        return _task_to_read(row) if row is not None else None
```

`session.get(Model, pk)` : récupération par clé primaire (utilise le cache d'identité de la
session si déjà chargée).

```python
    async def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
        stmt = select(TaskRow)
        if filters.status is not None:
            stmt = stmt.where(TaskRow.status == filters.status)
        ...
        if filters.q:
            like = f"%{filters.q}%"
            stmt = stmt.where(or_(TaskRow.title.ilike(like), TaskRow.description.ilike(like)))

        total = await self._session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )

        stmt = _apply_sort(stmt, filters.sort).limit(filters.limit).offset(filters.offset)
        rows = (await self._session.scalars(stmt)).all()
        return [_task_to_read(r) for r in rows], total or 0
```

- `select(TaskRow)` : la requête de base. On ajoute des `.where(...)` **conditionnellement**
  (chaque `.where` renvoie une **nouvelle** requête — les objets `Select` sont immuables).
- `.ilike("%...%")` : `LIKE` insensible à la casse.
- **le total** : on prend la requête filtrée, on lui enlève le tri (`.order_by(None)`,
  inutile pour compter), on l'emballe en sous-requête, et on `COUNT(*)` dessus. **Avant**
  `limit`/`offset`.
- `session.scalars(stmt)` : itérable d'objets `TaskRow`. `.all()` matérialise.
- coût du `total` : un `COUNT` complet. Sur des millions de lignes c'est lent → pagination
  *cursor* (Module 08).

```python
    async def update(self, task_id, changes) -> TaskRead | None:
        row = await self._session.get(TaskRow, task_id)
        if row is None:
            return None
        patch = changes.model_dump(exclude_unset=True)
        for key, value in patch.items():
            if key == "checklist" and value is not None:
                value = [v if isinstance(v, dict) else ChecklistItem.model_validate(v).model_dump()
                         for v in value]
            setattr(row, key, value)
        await self._session.flush()
        await self._session.refresh(row)
        return _task_to_read(row)
```

- `exclude_unset=True` : seuls les champs fournis (le PATCH correct, Module 02).
- `setattr(row, key, value)` : SQLAlchemy suit les modifications d'attributs → générera un
  `UPDATE` au `flush`.
- `checklist` : re-sérialisée en `list[dict]` pour la colonne JSON.
- `updated_at` : pas touché ici — `onupdate=utcnow` sur la colonne s'en charge au `flush`.

```python
    async def delete(self, task_id) -> bool:
        row = await self._session.get(TaskRow, task_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
```

`session.delete(row)` + `flush()` → `DELETE`. Toujours pas de commit.

### `SqlAlchemyProjectRepository.list` — le point N+1

```python
    async def list(self, *, limit, offset) -> tuple[list[ProjectRead], int]:
        count_col = func.count(TaskRow.id).label("task_count")
        stmt = (
            select(ProjectRow, count_col)
            .outerjoin(TaskRow, TaskRow.project_id == ProjectRow.id)
            .group_by(ProjectRow.id)
            .order_by(ProjectRow.id)
            .limit(limit).offset(offset)
        )
        total = await self._session.scalar(select(func.count()).select_from(ProjectRow))
        result = await self._session.execute(stmt)
        items = [ProjectRead(id=p.id, name=p.name, created_at=p.created_at, task_count=c)
                 for p, c in result.all()]
        return items, total or 0
```

- **une seule requête** pour tous les projets **et** leur nombre de tâches :
  `SELECT projects.*, COUNT(tasks.id) ... LEFT JOIN tasks ... GROUP BY projects.id`.
- `outerjoin` (LEFT JOIN) : les projets **sans** tâche apparaissent quand même (`count = 0`).
- `session.execute(stmt)` (et non `scalars`) car on sélectionne **2 choses** (`ProjectRow`
  + le compte) → chaque *row* est un tuple `(project, count)`.
- version naïve interdite : `for p in projects: p.task_count = len(p.tasks)` → 1 requête par
  projet.

---

## 8. `taskman/services/tasks.py` (async + transactions)

```python
class TaskService:
    def __init__(self, tasks: TaskRepository, uow: UnitOfWork) -> None:
        self._tasks = tasks
        self._uow = uow

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data)   # add + flush
        await self._uow.commit()                # <- valide la transaction
        return task

    async def get(self, task_id: int) -> TaskRead | None:
        return await self._tasks.get(task_id)   # lecture : AUCUN commit

    async def update(self, task_id, changes) -> TaskRead | None:
        task = await self._tasks.update(task_id, changes)
        if task is not None:                    # rien trouvé -> rien à committer
            await self._uow.commit()
        return task
```

- le service reçoit **`uow`** (= la session, vue comme `UnitOfWork`).
- **écritures** → `commit()` après. **lectures** → jamais.
- `update`/`delete` : on ne commit que si l'opération a **effectivement** modifié quelque
  chose (sinon `commit()` d'une transaction vide, inutile).
- si le repository lève (contrainte violée…), l'exception remonte, `commit()` n'est jamais
  atteint, et `get_session` ferme la session sans commit → **rollback**.

---

## 9. `taskman/api/deps.py`

```python
SessionDep = Annotated[AsyncSession, Depends(get_session)]

def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)

def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
    session: SessionDep,
) -> TaskService:
    return TaskService(tasks, uow=session)
```

- `get_task_repository` et `get_task_service` demandent **tous les deux** `get_session`.
- FastAPI **met en cache les sous-dépendances par requête** (`use_cache=True` par défaut) →
  **une seule** session est créée, partagée par le repo et le service.
- donc : le repo écrit sur la session `S`, le service commit la session `S`. Cohérent.

---

## 10. `taskman/main.py` (lifespan DB)

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    engine = create_engine(settings.database_url, echo=settings.db_echo)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()      # ferme le pool de connexions proprement
```

- le moteur est créé **une fois**, au démarrage. Créer un moteur par requête tuerait les
  perfs (pas de pool réutilisé).
- `app.state.session_factory` : ce que lit `get_session`.
- `await engine.dispose()` dans le `finally` : à l'arrêt (Ctrl+C, redéploiement), on ferme
  toutes les connexions du pool. Sans ça : connexions qui traînent côté PostgreSQL.
- `app.state.settings = settings` est posé dans `create_app` (avant le lifespan) — le
  lifespan en a besoin.

---

## 11. `alembic/env.py`

```python
import taskman.db.models  # noqa: F401   -> enregistre les tables dans Base.metadata
target_metadata = Base.metadata
```

Alembic compare `target_metadata` (tes modèles) à la base réelle. Il faut donc **importer
les modèles** pour qu'ils s'enregistrent.

```python
def _render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, TZDateTime):
        return "sa.DateTime(timezone=True)"
    return False
```

Sans ça, l'autogenerate écrit `taskman.db.base.TZDateTime()` dans la migration **sans
importer `taskman`** → `NameError` à l'exécution. On rend le type comme un simple
`sa.DateTime(timezone=True)` : dans la base, la colonne est identique ; la coercition UTC est
un comportement d'**exécution** de l'ORM, pas du schéma.

```python
async def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)   # Alembic est synchrone -> run_sync
    await engine.dispose()
```

Alembic est écrit en **synchrone**. `connection.run_sync(fn)` exécute `fn` (qui appelle
l'API Alembic) sur la connexion async, en faisant le pont.

```python
context.configure(connection=connection, target_metadata=target_metadata,
                  compare_type=True, render_as_batch=True, render_item=_render_item)
```

- `compare_type=True` : détecte aussi les changements de **type** de colonne.
- `render_as_batch=True` : SQLite ne sait pas faire `ALTER TABLE` complet → Alembic
  recrée la table (copie/rename). Indispensable pour migrer une base SQLite.

---

## 12. Les tests

```python
@pytest_asyncio.fixture
async def db_engine():
    engine = create_engine(TEST_DB_URL)              # sqlite+aiosqlite:// (mémoire, StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # crée les tables (rapide)
    yield engine
    await engine.dispose()
```

- `Base.metadata.create_all` : crée le schéma **directement** depuis les modèles (pas via
  Alembic — plus rapide). Un test séparé (`test_migrations.py`) vérifie que les migrations
  produisent **le même** schéma.

```python
@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app(Settings(env="test", database_url=TEST_DB_URL))
    async def _override_get_session():
        async with session_factory() as session:
            yield session
    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- on **surcharge `get_session`** pour utiliser le moteur de test (in-memory), pas celui que
  le `lifespan` créerait.
- `httpx.AsyncClient` + `ASGITransport` : appelle l'app **en async, dans le même event
  loop** que la base de test. `TestClient` (synchrone) crée sa propre boucle → conflits avec
  l'async SQLite. (Module 07 détaille tout ça.)

```python
async def test_create_unknown_project_fails(client):
    with pytest.raises(IntegrityError):
        await client.post("/tasks", json={"title": "x", "project_id": 999})
```

FK activée → `INSERT` refusé → `IntegrityError` **remonte brute** (pas encore de handler).
Le Module 05 la transformera en `409 Conflict` propre.

```python
@pytest.mark.slow
def test_no_pending_migration(tmp_path):
    # alembic upgrade head  puis  alembic check  -> doit être "no new upgrade operations"
```

Le garde-fou : si tu changes un modèle sans générer la migration → ce test échoue.

---

## Ce qui change au Module 05

| Ici (Module 04) | Module 05 |
|---|---|
| `IntegrityError` remonte brute → 500 | exception métier `ConflictError` → `409` propre |
| `None` du service → `raise HTTPException(404)` dans la route | `TaskNotFoundError` → handler central |
| pas de corrélation dans les logs | `request-id` + logs JSON |
| format d'erreur = défaut FastAPI | format unifié (Problem Details / RFC 9457) |
