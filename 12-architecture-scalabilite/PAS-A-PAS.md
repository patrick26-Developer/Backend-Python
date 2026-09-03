# Module 12 — Explication pas à pas

> Nouveaux : `domain/events.py`, `outbox.py`, `realtime.py`, `api/idempotency.py`,
> `api/routes/{events,v2}.py`, `docs/adr/*`. Modifiés : `db/models.py` (`OutboxRow`),
> `services/tasks.py`, `api/deps.py`, `main.py`.

---

## 1. `taskman/domain/events.py`

```python
class DomainEvent(BaseModel):
    model_config = {"frozen": True}
    type: str            # "task.completed"
    payload: dict[str, Any]
```

- `frozen=True` : un événement est un **fait passé**, immuable.
- `type` : nom convention `<agrégat>.<verbe au passé>` (`task.completed`, `project.archived`).
- `payload` : les données minimales pour que le consommateur agisse (`task_id`, pas toute la
  tâche — elle a pu changer entre l'émission et la consommation).

```python
class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self) -> AsyncGenerator[DomainEvent, None]: ...
```

`subscribe` est `def` (pas `async def`) : une fonction génératrice async **a** ce type.

---

## 2. `taskman/outbox.py` — l'outbox pattern

### Le problème résolu

```python
# NAÏF — deux écritures dans deux systèmes, pas de transaction commune :
await repo.save(task)          # ← DB committée
await broker.publish(event)    # ← si ça plante, l'événement est PERDU
```

### La solution

```python
class SqlAlchemyOutboxRepository:
    async def add(self, event):
        self._session.add(OutboxRow(event_type=event.type, payload=event.payload))
        await self._session.flush()          # dans LA transaction courante
```

L'événement est une **ligne de table**, écrite dans la **même transaction** que la tâche.
`TaskService.complete` :

```python
task = await self._tasks.mark_completed(task_id)
await self._outbox.add(DomainEvent("task.completed", {...}))
await self._uow.commit()          # tâche + événement : TOUT OU RIEN
```

Si le `commit` échoue → ni la tâche ni l'événement. Pas de désynchronisation possible.

### Le drain

```python
async def drain_outbox(outbox, publisher, session_commit, *, batch=100):
    pending = await outbox.list_unpublished(limit=batch)
    for _id, event in pending:
        await publisher.publish(event)
    await outbox.mark_published([i for i, _ in pending])
    await session_commit.commit()
    return len(pending)
```

Un worker `taskiq` périodique l'appelle toutes les N secondes. Garantie **at-least-once** :
si le worker meurt entre `publish` et `mark_published`, les mêmes événements seront republiés
→ **les consommateurs doivent être idempotents**.

### Le complément « best-effort »

`TaskService.complete` fait **aussi** `await self._events.publish(event)` **après** le commit,
pour le temps réel **immédiat** (SSE). Si ça échoue, tant pis — l'outbox rattrapera. L'outbox
reste la **source de vérité**.

---

## 3. `taskman/realtime.py` — fan-out SSE

```python
class InMemoryEventPublisher:
    def __init__(self):
        self._subscribers: set[asyncio.Queue[DomainEvent]] = set()

    async def publish(self, event):
        for queue in list(self._subscribers):
            queue.put_nowait(event)

    async def subscribe(self):
        queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)   # nettoyage à la déconnexion
```

- une `asyncio.Queue` **par abonné** (chaque connexion SSE). `publish` pousse dans toutes.
- `maxsize=100` : si un client est trop lent, `put_nowait` lèverait → on préfère **perdre**
  un événement pour un client lent que bloquer les autres (choix assumé).
- **mono-process** : un client connecté à l'instance A ne voit pas un événement publié sur
  l'instance B.

```python
class RedisEventPublisher:
    async def publish(self, event):
        await self._redis.publish("taskman:events", event.model_dump_json())

    async def subscribe(self):
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("taskman:events")
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield DomainEvent(**json.loads(message["data"]))
```

**Multi-instance** : chaque instance publie sur le canal Redis ; chaque instance écoute et
relaie à **ses** clients SSE. Fan-out complet.

---

## 4. `taskman/api/routes/events.py` — SSE

```python
@router.get("")
async def stream_events(request, _user: CurrentUser, publisher: EventPublisherDep):
    async def _generator():
        yield {"event": "connected", "data": "{}"}          # confirme l'établissement
        subscription = publisher.subscribe()
        try:
            async for event in subscription:
                if await request.is_disconnected():
                    break
                yield {"event": event.type, "data": event.model_dump_json()}
        finally:
            with contextlib.suppress(Exception):
                await subscription.aclose()
    return EventSourceResponse(_generator(), ping=15)
```

- `EventSourceResponse` (`sse-starlette`) : une réponse HTTP qui **ne se ferme pas**. Chaque
  `yield {"event", "data"}` devient un bloc SSE `event: ...\ndata: ...\n\n`.
- **1er message immédiat** (`connected`) : le client sait que la connexion tient (utile en
  test, et pour l'UI).
- `request.is_disconnected()` : on arrête la boucle si le client part → on ne fuit pas la
  souscription.
- `ping=15` : un commentaire SSE toutes les 15 s pour garder la connexion ouverte à travers
  les proxies.
- authentifié (`_user: CurrentUser`).

---

## 5. `taskman/api/idempotency.py`

```python
class IdempotencyMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH"}:
            return await self.app(scope, receive, send)
        key = Request(scope).headers.get("idempotency-key")
        if not key:
            return await self.app(scope, receive, send)
        cache_key = f"idem:{scope['method']}:{path}:{key}"

        stored = await cache.get(cache_key)
        if stored is not None:                    # REJEU -> on renvoie la réponse d'origine
            data = json.loads(stored)
            await send({"type": "http.response.start", "status": data["status"],
                        "headers": [...(b"idempotent-replay", b"true")]})
            await send({"type": "http.response.body", "body": data["body"].encode()})
            return

        # 1er appel : on exécute et on CAPTURE la réponse
        chunks = []
        async def send_wrapper(message):
            if message["type"] == "http.response.start": status_code = message["status"]; headers = ...
            elif message["type"] == "http.response.body": chunks.append(message["body"])
            await send(message)
        await self.app(scope, receive, send_wrapper)

        if 200 <= status_code < 300 and len(body) <= _MAX_STORED_BODY:
            await cache.set(cache_key, json.dumps({...}), ttl=24*3600)
```

- n'agit que sur `POST`/`PATCH` **avec** `Idempotency-Key` (le client génère la clé).
- **rejeu** : la route **n'est pas exécutée** → pas de 2ᵉ création. On renvoie l'octet près
  la réponse d'origine + `Idempotent-Replay: true`.
- **on ne mémorise que les 2xx** : une erreur (4xx/5xx) doit pouvoir être re-tentée.
- TTL 24 h : au-delà, une même clé re-crée (le client a « oublié »).
- on ne garde que `Content-Type` et `Location` dans les en-têtes stockés (pas le
  `x-request-id` qui doit rester propre à chaque appel).

---

## 6. Versionnage — `taskman/main.py`

```python
# infrastructure : PAS de version
app.include_router(meta.router)   # /
app.include_router(ops.router)    # /health /ready /metrics

# métier : sous /v1
v1 = APIRouter(prefix="/v1")
for r in (auth.router, admin.router, projects.router, tasks.router, events.router):
    v1.include_router(r)
app.include_router(v1)

# /v2 : contrat modifié, coexiste
app.include_router(v2.router, prefix="/v2")
```

- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/login")` → le bouton « Authorize »
  de Swagger tape la bonne URL.
- `response.headers["Location"] = request.url_for("get_task", task_id=...).path` : `url_for`
  résout le **chemin complet** (`/v1/tasks/{id}` + `root_path` éventuel) — on ne hardcode
  plus `/tasks/{id}`.

### `v2.py` — un endpoint au contrat changé

```python
class TaskReadV2(BaseModel):
    overdue: bool                     # v1 : "is_overdue"
    checklist_total: int              # v1 : "checklist" (la liste complète)
    checklist_done: int

@router.get("/{task_id}")
async def get_task_v2(task_id, service: TaskServiceDep) -> TaskReadV2:
    task = await service.get(task_id)     # MÊME couche service que v1
    return TaskReadV2(overdue=task.is_overdue,
                      checklist_total=len(task.checklist),
                      checklist_done=sum(1 for i in task.checklist if i.done), ...)
```

On **ne duplique pas** le CRUD : v2 partage `TaskService`, seul le **schéma de sortie**
change. C'est ça, faire cohabiter deux versions à coût maîtrisé.

---

## 7. `TaskService` — le smell assumé

```python
def __init__(self, tasks, uow, actor, cache, outbox, events):
```

6 collaborateurs → le signe qu'on gagnerait à séparer **commandes** (`create`, `complete`,
`delete` — besoin de `uow`, `outbox`, `events`) et **requêtes** (`get`, `list`, `stats` —
besoin de `cache` seulement). C'est un **CQRS léger**. On l'a laissé en un seul service pour
garder un point d'entrée unique — mais c'est documenté comme dette (exercice 12.1 le
corrige avec la réorganisation en modules).

---

## 8. Les tests

```python
async def test_complete_writes_event_in_same_transaction(member_client, session_factory):
    ... POST /v1/tasks/{id}/complete ...
    async with session_factory() as s:
        rows = (await s.scalars(select(OutboxRow))).all()
    assert rows[0].event_type == "task.completed"
    assert rows[0].published_at is None       # écrit, pas encore drainé

async def test_idempotency_key_replays_response(member_client):
    r1 = await member_client.post("/v1/tasks", json=body, headers={"Idempotency-Key": "abc"})
    r2 = await member_client.post("/v1/tasks", json=body, headers={"Idempotency-Key": "abc"})
    assert r1.json()["id"] == r2.json()["id"]         # UNE ressource
    assert r2.headers["idempotent-replay"] == "true"
    assert (await member_client.get("/v1/tasks")).json()["total"] == 1

async def test_v1_and_v2_coexist(member_client):
    v1 = (await member_client.get(f"/v1/tasks/{tid}")).json()
    v2 = (await member_client.get(f"/v2/tasks/{tid}")).json()
    assert "is_overdue" in v1 and "overdue" in v2 and "is_overdue" not in v2

@pytest.mark.slow
async def test_sse_stream_delivers_events(app):
    async with listener.stream("GET", "/v1/events") as resp:
        ... trigger complete from another client ...
        assert "task.completed" in events
```

---

## C'est fini.

`taskman` est passé de « un CRUD en mémoire » à une API :
structurée, validée, testée, persistée, authentifiée, observable, durcie, déployable,
scalable. Tu as vu **pourquoi** chaque brique, pas seulement comment.

**L'examen** : refais-le de zéro, en 2 jours, sans regarder. Voir [`THEORIE.md`](THEORIE.md) §10.
