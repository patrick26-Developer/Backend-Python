# Module 07 — Explication pas à pas

> Ce module ajoute peu de code applicatif (une action `complete`) et beaucoup
> d'**infrastructure de test**. On explique chaque fichier.

---

## 1. `pyproject.toml` — configuration des tests

```toml
[tool.pytest.ini_options]
pythonpath = ["."]          # rend `import tests.factories` possible
testpaths = ["tests"]
asyncio_mode = "auto"       # les tests async tournent sans décorateur
markers = [
    "slow: ...",            # -m "not slow"
    "e2e: ...",             # -m "not e2e"
]
filterwarnings = ["error", "ignore::...StarletteDeprecationWarning"]
```

- `pythonpath = ["."]` : ajoute la racine au `sys.path` des tests → `tests/` est un paquet
  importable (fabriques partagées).
- `filterwarnings = ["error"]` : **tout avertissement fait échouer** la suite. Discipline :
  un `DeprecationWarning` non traité = une dette qu'on voit tout de suite. On *ignore*
  nommément ceux des libs qu'on ne contrôle pas.

```toml
[tool.coverage.run]
branch = true               # couverture des BRANCHES, pas seulement des lignes

[tool.coverage.report]
fail_under = 85             # la CI échoue en-dessous
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "\\.\\.\\.$"]
```

- `branch = true` : `if x:` compte pour **2** (branche vraie ET fausse). Sans ça, on peut
  avoir « 100 % de lignes » sans jamais tester le `else`.
- `exclude_also` : les lignes qu'il est inutile de couvrir — `if TYPE_CHECKING:` (jamais
  exécuté au *runtime*), les `...` des `Protocol`.
- `fail_under = 85` : **le seuil qui bloque**. Un PR qui fait chuter la couverture ne passe
  pas.

---

## 2. `tests/factories.py`

```python
_seq = 0
def _next() -> int:
    global _seq
    _seq += 1
    return _seq

def task_payload(**over: Any) -> dict[str, Any]:
    n = _next()
    return {"title": f"Tâche {n}", "project_id": 1} | over
```

- `_next()` : un compteur global → chaque appel produit un titre **unique** (pas de
  collision entre tests qui listent/filtrent).
- `{...} | over` : les valeurs par défaut, **écrasées** par ce que le test précise.
  `task_payload(priority=5)` → tout par défaut sauf `priority`.
- `make_task_create(**over)` : la version « schéma Pydantic » pour les tests **unitaires**
  (qui ne passent pas par HTTP).

**Pourquoi** : si demain `TaskCreate` gagne un champ obligatoire, on corrige `task_payload`
**une** fois au lieu de 40 tests.

---

## 3. L'action `complete` — le code minimal (phase « Vert » du TDD)

### `taskman/db/models.py`

```python
completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
```

Une colonne nullable : `None` tant que la tâche n'est pas terminée.

### `taskman/schemas/task.py`

```python
class TaskRead(TaskBase):
    ...
    completed_at: datetime | None = None
```

Ajouté **uniquement** à `TaskRead` (sortie). Pas à `TaskCreate`/`TaskUpdate` : le client ne
fixe pas cette date, c'est le serveur.

### `taskman/repositories/` — `mark_completed`

```python
# base.py (Protocol)
async def mark_completed(self, task_id: int) -> TaskRead | None: ...

# sqlalchemy.py
async def mark_completed(self, task_id: int) -> TaskRead | None:
    row = await self._session.get(TaskRow, task_id)
    if row is None:
        return None
    row.status = TaskStatus.done
    row.completed_at = datetime.now(UTC)
    await self._session.flush()
    await self._session.refresh(row)
    return _task_to_read(row)
```

Une **méthode dédiée** plutôt que de passer par `update(TaskUpdate)` : `completed_at` n'est
pas dans `TaskUpdate` (champ serveur), et « terminer une tâche » est une **action métier**
nommée, pas un `PATCH` générique. Le repo pose les deux champs et `flush` (pas de `commit` —
c'est le service).

### `taskman/services/tasks.py` — `complete`

```python
async def complete(self, task_id: int) -> TaskRead:
    await self._assert_can_access(task_id)      # sécurité : la tâche est-elle à moi ?
    task = await self._tasks.mark_completed(task_id)
    assert task is not None                     # garanti par _assert_can_access
    await self._uow.commit()                    # frontière transactionnelle
    return task
```

Réutilise `_assert_can_access` du Module 06 → un `member` ne peut pas terminer la tâche d'un
autre (404). Puis délègue, puis `commit`.

### `taskman/api/routes/tasks.py` — la route

```python
@router.post("/{task_id}/complete")
async def complete_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    return await service.complete(task_id)
```

`POST` (et non `PATCH`) : c'est une **action**, pas une modification arbitraire de champs.
Une ligne. `TaskServiceDep` (Module 06) exige déjà l'authentification.

### Migration

```bash
alembic revision --autogenerate -m "task completed_at"
```

Détecte `Detected added column 'tasks.completed_at'`. **Incrémentale** cette fois (on ne
squash plus — au Module 06 c'était légitime car rien n'était déployé). Le fichier est à
relire, puis `alembic upgrade head`.

---

## 4. `tests/integration/test_complete_action.py` (phase « Rouge », écrite en premier)

```python
async def test_complete_sets_status_and_timestamp(member_client: AsyncClient) -> None:
    pid = await _project(member_client)
    tid = (await member_client.post("/tasks", json=task_payload(project_id=pid))).json()["id"]

    before = await member_client.get(f"/tasks/{tid}")
    assert before.json()["completed_at"] is None      # état initial

    resp = await member_client.post(f"/tasks/{tid}/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["completed_at"] is not None
```

- écrit **avant** la route → il échoue (405 Method Not Allowed, puis 200 une fois codé).
- teste le **comportement observable** (le JSON de la réponse), pas l'implémentation.
- `test_complete_is_persisted` : un `GET` **ultérieur** confirme que ce n'est pas qu'en
  mémoire → prouve le `commit`.
- `test_cannot_complete_another_users_task` : réutilise le patron BOLA du Module 06 → 404.

---

## 5. `tests/e2e/test_postgres.py`

```python
pytestmark = pytest.mark.e2e     # tout le fichier est marqué "e2e"

@pytest.fixture(scope="module")
def postgres_url():
    tc = pytest.importorskip("testcontainers.postgres")
    try:
        container = tc.PostgresContainer("postgres:17-alpine", driver="asyncpg")
        container.start()
    except Exception as exc:
        pytest.skip(f"Docker indisponible : {exc}")
    yield container.get_connection_url()
    container.stop()
```

- `pytest.importorskip(...)` : si `testcontainers` n'est pas installé → *skip*, pas *fail*.
- `try/except → pytest.skip` : si Docker n'est pas démarré → *skip*. **Jamais** un échec
  rouge pour « pas de Docker » — sinon la CI locale sans Docker est bloquée.
- `scope="module"` : **un seul** conteneur pour tout le fichier (démarrer PostgreSQL prend
  ~2 s).

```python
@pytest_asyncio.fixture
async def pg_engine(postgres_url):
    engine = create_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # repart propre
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
```

`drop_all` + `create_all` entre les tests du module → isolation (le conteneur, lui, est
partagé).

```python
async def test_full_flow_on_real_postgres(pg_client):
    await pg_client.post("/tasks", json={"title": "Documenter l'ARCHItecture", ...})
    page = (await pg_client.get("/tasks", params={"q": "archi"})).json()
    assert page["total"] == 1        # ILIKE réel de PostgreSQL (SQLite le simule)
```

Ce que SQLite **ne** garantit **pas** et qu'on vérifie ici : `ILIKE` insensible à la casse,
les contraintes FK strictes, le rollback transactionnel réel.

---

## 6. Le workflow TDD, visible dans git

```
$ git log --oneline
abc123  test(module-07): tests de l'action complete (rouge)   <- tests SEULS
def456  feat(module-07): action complete (vert)               <- implémentation
```

Deux commits. Le premier ne contient **que** des tests qui échouent. C'est la preuve du TDD.

---

## Ce qui vient au Module 08

Le Module 08 utilise l'action `complete` comme déclencheur d'un **effet de bord** : à la
complétion, envoyer une notification. D'abord via `BackgroundTasks`, puis via un vrai
worker. Et on teste ça — avec un *mock* cette fois (vérifier qu'un e-mail « aurait » été
envoyé).
