# Module 08 — Explication pas à pas

> Fichiers **nouveaux** : `core/cache.py`, `services/notifications.py`, `tasks.py`,
> `worker.py`. **Modifiés** : `schemas/task.py`, `repositories/*`, `services/tasks.py`,
> `api/{deps,routes/tasks,routes/projects}.py`, `main.py`, `core/config.py`.

---

## 1. `taskman/core/cache.py`

```python
class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_prefix(self, prefix: str) -> None: ...
    async def close(self) -> None: ...
```

Le service dépendra de **`Cache`**, jamais de Redis. Les valeurs sont des **`str`** (on
sérialise en JSON au-dessus) → l'interface reste triviale.

```python
class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}   # key -> (expires_at, value)

    async def get(self, key):
        item = self._store.get(key)
        if item is None: return None
        expires_at, value = item
        if expires_at < time.monotonic():
            self._store.pop(key, None); return None
        return value
```

- `time.monotonic()` : horloge **monotone** (pas d'heure système) → le TTL est fiable même
  si l'horloge saute.
- expiration **paresseuse** : on ne purge que ce qu'on relit. Pour un vrai LRU, il faudrait
  un `cachetools`, mais pour un cache applicatif court c'est suffisant.

```python
class RedisCache:
    def __init__(self, url):
        import redis.asyncio as redis
        self._redis = redis.from_url(url, decode_responses=True)

    async def delete_prefix(self, prefix):
        async for key in self._redis.scan_iter(match=f"{prefix}*"):
            await self._redis.delete(key)
```

`scan_iter` (curseur) et **pas** `KEYS` : `KEYS` parcourt **toute** la base d'un coup et la
**bloque** — interdit en prod. `SCAN` avance par petits lots.

```python
def build_cache(redis_url: str | None) -> Cache:
    return RedisCache(redis_url) if redis_url else InMemoryCache()
```

Un seul point de choix. `taskman/main.py` : `app.state.cache = build_cache(settings.redis_url)`.

---

## 2. Agrégats mis en cache — `taskman/services/tasks.py`

```python
class TaskService:
    def __init__(self, tasks, uow, actor, cache: Cache) -> None:
        ...
        self._cache = cache

    async def stats(self, project_id: int) -> TaskStats:
        key = f"project:{project_id}:stats"
        if (cached := await self._cache.get(key)) is not None:
            return TaskStats.model_validate_json(cached)          # HIT

        by_status, overdue = await self._tasks.project_stats(project_id)   # MISS -> calcul
        total = sum(by_status.values())
        stats = TaskStats(project_id=project_id, total=total, by_status=by_status,
                          overdue=overdue,
                          completion_rate=round(by_status.get("done", 0) / total, 3) if total else 0.0)
        await self._cache.set(key, stats.model_dump_json(), ttl=_STATS_TTL)  # 60 s
        return stats
```

C'est le patron **cache-aside** : lire le cache → sinon calculer → écrire le cache. Le
sérialisation passe par `model_dump_json` / `model_validate_json` (Pydantic).

### L'invalidation

```python
    async def _invalidate_project(self, project_id: int) -> None:
        await self._cache.delete(f"project:{project_id}:stats")

    async def create(self, data):
        task = await self._tasks.create(data, owner_id=self._actor.id)
        await self._uow.commit()
        await self._invalidate_project(task.project_id)   # <- les stats du projet changent
        return task
```

**Chaque écriture** qui affecte les stats d'un projet (`create`, `update`, `complete`,
`delete`) supprime la clé. Sans ça, le TTL de 60 s laisserait des stats fausses affichées
jusqu'à une minute. La stratégie est **écrite** (clé unique par projet, invalidée par 4
événements) — pas juste « on met un TTL et on espère ».

### `project_stats` dans le repository — **1 requête**, pas N

```python
# sqlalchemy.py
async def project_stats(self, project_id):
    by_status_rows = await self._session.execute(
        select(TaskRow.status, func.count())
        .where(TaskRow.project_id == project_id)
        .group_by(TaskRow.status)
    )
    by_status = {str(s): c for s, c in by_status_rows.all()}
    overdue = await self._session.scalar(select(func.count()).where(and_(...)))
    return by_status, overdue
```

Un `GROUP BY status` (une requête) + un `COUNT` pour les retards. **Pas** de boucle Python
sur les tâches.

---

## 3. Pagination *cursor* — `taskman/services/tasks.py`

```python
def _encode_cursor(created_at: datetime, task_id: int) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": task_id}).encode()
    return base64.urlsafe_b64encode(raw).decode()

def _decode_cursor(token: str) -> tuple[datetime, int]:
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()))
        return datetime.fromisoformat(data["c"]), int(data["i"])
    except (ValueError, KeyError, TypeError) as exc:
        raise BadRequestError("cursor invalide") from exc
```

Le *cursor* = **base64(JSON)** de la dernière ligne vue. **Opaque** pour le client : il ne
doit pas le construire, juste le renvoyer. Illisible → `BadRequestError` (400).

```python
async def list(self, filters: TaskFilters) -> TaskPage:
    if not self._use_keyset(filters):                 # tri arbitraire / offset -> ancien mode
        items, total = await self._tasks.list_page(filters, owner_id=self._scope)
        return TaskPage(items=items, total=total, ...)

    after = _decode_cursor(filters.cursor) if filters.cursor else None
    rows = await self._tasks.list_keyset(owner_id=self._scope, limit=filters.limit, after=after)
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == filters.limit else None
    return TaskPage(items=rows, total=len(rows), next_cursor=next_cursor, ...)
```

- mode keyset si `cursor` fourni **ou** (1re page, tri `-created_at`) ;
- `next_cursor` **seulement** si on a rempli la page (`len == limit`) — sinon on est au bout.

```python
# repository (sqlalchemy.py)
async def list_keyset(self, *, owner_id, limit, after):
    stmt = select(TaskRow)
    if owner_id is not None:
        stmt = stmt.where(TaskRow.owner_id == owner_id)
    if after is not None:
        stmt = stmt.where(tuple_(TaskRow.created_at, TaskRow.id) < after)   # <- KEYSET
    stmt = stmt.order_by(TaskRow.created_at.desc(), TaskRow.id.desc()).limit(limit)
    return [_task_to_read(r) for r in (await self._session.scalars(stmt)).all()]
```

`tuple_(created_at, id) < (last_created_at, last_id)` : compare le **couple** (comparaison
lexicographique SQL). Avec un index sur `(created_at, id)`, la base saute directement à la
bonne position → **temps constant** quelle que soit la profondeur (contrairement à
`OFFSET 100000`).

---

## 4. Export streamé — `taskman/api/routes/tasks.py`

```python
@router.get("/export")
async def export_tasks(service: TaskServiceDep) -> StreamingResponse:
    async def _lines() -> AsyncIterator[bytes]:
        async for task in service.export():
            yield (task.model_dump_json() + "\n").encode()
    return StreamingResponse(_lines(), media_type="application/x-ndjson")
```

- `StreamingResponse` d'un **générateur async** : FastAPI envoie chaque `yield` au fil de
  l'eau. La mémoire du serveur reste **constante** même pour 1 million de tâches.
- **NDJSON** : un objet JSON **par ligne**. Le client lit ligne par ligne.
- **ordre des routes** : `/tasks/export` est déclaré **avant** `/tasks/{task_id}` — sinon
  FastAPI essaie de convertir `"export"` en `int` (le type de `task_id`) et renvoie 422.

```python
# repository
async def iter_by_owner(self, owner_id):
    result = await self._session.stream_scalars(select(TaskRow)...)   # curseur SERVEUR
    async for row in result:
        yield _task_to_read(row)
```

`stream_scalars` : un **curseur côté base** — les lignes arrivent par lots, jamais toutes en
RAM. `.scalars().all()` chargerait tout.

> Note mypy : dans le `Protocol`, `iter_by_owner` se déclare `def ... -> AsyncIterator[...]`
> (pas `async def`) — une fonction génératrice async **a** ce type.

---

## 5. Tâche de fond — `taskman/api/routes/tasks.py`

```python
@router.post("/{task_id}/complete")
async def complete_task(task_id, service, notifier: NotifierDep, background: BackgroundTasks):
    task = await service.complete(task_id)
    background.add_task(notifier.task_completed, task)   # APRÈS l'envoi de la réponse
    return task
```

- `BackgroundTasks` (injecté par FastAPI) : `add_task(fn, *args)` planifie `fn` pour
  **après** que la réponse est partie. Le client n'attend pas.
- **limites** (voir THEORIE) : même process, pas de *retry*, perdu si le process meurt. OK
  pour une notification non critique.

### Le worker (pour quand ça ne suffit plus) — `taskman/tasks.py`

```python
broker: AsyncBroker = (
    ListQueueBroker(settings.redis_url) if settings.redis_url else InMemoryBroker()
)

@broker.task
async def notify_task_completed(task_id: int, assignee_email: str | None) -> None:
    _logger.info("notification", extra={"task_id": task_id, ...})
```

- `InMemoryBroker` (défaut, sans Redis) : la tâche tourne dans le process → dev, tests.
- `ListQueueBroker` (Redis) : l'API `await notify_task_completed.kiq(...)` **publie** ;
  `taskiq worker taskman.worker:broker` **consomme**.
- **idempotence** : le broker garantit *at-least-once* → la tâche peut tourner 2 fois. Ici
  elle ne fait qu'écrire un log (rien d'irréversible). Un vrai envoi d'e-mail devrait
  vérifier un marqueur « déjà envoyé » (clé de cache, colonne DB).

---

## 6. `taskman/main.py`

```python
app.add_middleware(GZipMiddleware, minimum_size=1024)   # compresse les réponses > 1 Kio
```

Ajouté **avant** `RequestContextMiddleware` → GZip est *interne* (il compresse la réponse
finale, RequestContext ajoute son entête par-dessus).

```python
@asynccontextmanager
async def lifespan(app):
    ...
    app.state.cache = build_cache(settings.redis_url)
    from taskman.tasks import broker
    if not broker.is_worker_process:
        await broker.startup()
    try:
        yield
    finally:
        if not broker.is_worker_process:
            await broker.shutdown()
        await app.state.cache.close()
        await engine.dispose()
```

- `broker.is_worker_process` : `False` dans l'API (on démarre juste le *client*), `True`
  quand c'est la CLI `taskiq worker` qui tourne (elle gère elle-même le cycle de vie).
- tout est fermé proprement à l'arrêt : cache, broker, moteur DB.

---

## 7. Les tests

```python
# tests/conftest.py — le lifespan ne tourne pas avec ASGITransport :
application.state.cache = InMemoryCache()
```

```python
async def test_stats_cache_invalidated_on_new_task(member_client):
    pid = ...
    await member_client.post("/tasks", json=task_payload(project_id=pid))
    assert (await member_client.get(f"/projects/{pid}/stats")).json()["total"] == 1   # met en cache "1"
    await member_client.post("/tasks", json=task_payload(project_id=pid))              # invalide
    assert (await member_client.get(f"/projects/{pid}/stats")).json()["total"] == 2   # recalculé
```

Sans l'invalidation, la 2ᵉ assertion lirait encore `1` (depuis le cache). **C'est ce test
qui prouve que l'invalidation marche.**

```python
async def test_cursor_pagination(member_client):
    seen = set()
    params = {"limit": 2, "sort": "-created_at"}
    for _ in range(10):
        page = (await member_client.get("/tasks", params=params)).json()
        seen.update(t["id"] for t in page["items"])
        if not page["next_cursor"]: break
        params = {..., "cursor": page["next_cursor"]}
    assert len(seen) == 5   # tout vu, une seule fois
```

```python
monkeypatch.setattr(LoggingNotifier, "task_completed", _spy)   # _spy(self, task)
...
assert seen == [tid]   # la tâche de fond a bien tourné
```

Ici on **mocke** (`monkeypatch`) — légitime : on vérifie qu'un effet de bord *a eu lieu*,
pas une valeur de retour.

---

## Ce qui vient au Module 09

Le Module 08 a ajouté des composants (cache, broker). Le Module 09 les rend **observables** :
métriques Prometheus (latence, taux d'erreur), traces, et surtout `/ready` qui vérifie que
la DB **et** Redis répondent.
