# Module 08 — Async avancé & performance

> **Objectif** : savoir **identifier un goulot d'étranglement** et choisir la bonne parade.
> Tâches de fond, workers, cache, pagination *cursor*, chasse au N+1, streaming.
> `async` mal utilisé est **plus lent** que du sync.
>
> **Durée estimée** : 12 à 16 h.
> **Pré-requis** : Modules 04 (DB async) et 07 (tests).

---

## 1. L'*event loop*, précisément

Un worker ASGI exécute **une** boucle d'événements. Elle fait tourner des coroutines : dès
qu'une coroutine `await` une I/O, la boucle passe à une autre. **Un seul thread**, mais des
centaines de requêtes « en vol ».

### Ce qui **bloque** la boucle (interdit dans une route `async`)

| Bloquant | Pourquoi | Parade |
|---|---|---|
| `time.sleep(1)` | fige le thread 1 s | `await asyncio.sleep(1)` |
| `requests.get(url)` | I/O **synchrone** | `httpx.AsyncClient` |
| driver DB sync (`psycopg2`) | idem | `asyncpg` / `aiosqlite` |
| gros calcul CPU (parsing 50 Mo, crypto, image) | monopolise le thread | `await asyncio.to_thread(fn, ...)` ou un worker |
| lecture de fichier avec `open().read()` | I/O sync | `await asyncio.to_thread` ou `aiofiles` |

**Un seul** appel bloquant dans **une** requête gèle **toutes** les autres pendant sa durée.

### `def` vs `async def` dans FastAPI

- `async def` : exécutée **dans** la boucle. Tu es responsable de ne rien bloquer.
- `def` (route synchrone) : FastAPI l'exécute dans un **threadpool** → elle ne bloque pas la
  boucle, mais le pool est limité (~40 threads). Utile pour du code legacy sync.
- Une dépendance `def` : threadpool aussi.

Règle : **tout async, ou assume le threadpool** — pas de mélange accidentel.

### Mesurer

```python
create_async_engine(url, echo=True)     # compte les requêtes SQL
```

Pour le temps : le middleware `duration_ms` du Module 05. Pour le profil : `py-spy`,
`austin`. Pour la charge : `locust`, `k6`.

---

## 2. Tâches de fond : `BackgroundTasks`

« Répondre au client **maintenant**, faire le travail lent **après** l'envoi de la réponse. »

```python
from fastapi import BackgroundTasks

@router.post("/{task_id}/complete")
async def complete(task_id: TaskId, service: TaskServiceDep, background: BackgroundTasks) -> TaskRead:
    task = await service.complete(task_id)
    background.add_task(notifier.task_completed, task)   # exécuté APRÈS la réponse
    return task
```

- s'exécute **dans le même process**, **après** que la réponse est partie.
- **limites** : pas de reprise si le process meurt ; pas de *retry* ; si la tâche est lente,
  elle occupe le worker ; pas de visibilité.
- **bon pour** : envoyer un e-mail, invalider un cache, écrire un log d'audit — des choses
  rapides et non critiques.

### Tester une tâche de fond

Avec un **mock** (ici c'est légitime — on vérifie qu'un appel « aurait » eu lieu) :

```python
def test_complete_triggers_notification(member_client, monkeypatch):
    calls = []
    monkeypatch.setattr(notifier, "task_completed", lambda t: calls.append(t.id))
    ...
    assert calls == [task_id]
```

---

## 3. Workers externes : `taskiq` / `ARQ` / Celery

Quand la tâche est **critique** (doit s'exécuter même si l'API redémarre), **lente**
(minutes), ou **planifiée** → sors-la du process API.

```
API  ──push──▶  broker (Redis)  ──pull──▶  worker(s)  ──▶  résultat
```

`taskiq` (async-natif, moderne) :

```python
# taskman/worker.py
broker = ListQueueBroker(settings.redis_url)   # ou InMemoryBroker() en test

@broker.task
async def send_completion_email(task_id: int, email: str) -> None:
    ...   # tourne dans le PROCESS worker, pas l'API

# côté API
await send_completion_email.kiq(task.id, task.assignee_email)
```

- l'API **publie** et rend la main immédiatement.
- un ou plusieurs **workers** (`taskiq worker taskman.worker:broker`) consomment.
- *retry*, *dead-letter*, planification, priorités : gérés par le broker/lib.
- **coût** : un composant de plus (Redis) + un process de plus + la complexité du
  *at-least-once* (une tâche peut s'exécuter 2 fois → **rends-la idempotente**).

| Besoin | Solution |
|---|---|
| e-mail non critique, < 1 s | `BackgroundTasks` |
| e-mail critique / avec retry | worker |
| traitement de minutes | worker |
| tâche planifiée (rapport quotidien) | worker + scheduler (Module 09 / `schedule`) |

---

## 4. Cache

### `cache-aside` (le patron par défaut)

```
lire ──▶ dans le cache ? ── oui ──▶ renvoyer
                        └─ non ──▶ lire la source ──▶ écrire dans le cache (TTL) ──▶ renvoyer
```

```python
async def project_stats(project_id: int) -> Stats:
    key = f"project:{project_id}:stats"
    if (cached := await cache.get(key)) is not None:
        return Stats.model_validate_json(cached)
    stats = await compute_stats(project_id)          # coûteux (agrégations SQL)
    await cache.set(key, stats.model_dump_json(), ttl=60)
    return stats
```

### L'**invalidation**, le vrai sujet

> « Il n'y a que deux choses difficiles en informatique : l'invalidation de cache et nommer
> les choses. »

Un TTL seul → données périmées jusqu'à N secondes. Il faut **invalider activement** quand la
source change :

```python
async def complete(self, task_id):
    task = await self._tasks.mark_completed(task_id)
    await self._cache.delete_prefix(f"project:{task.project_id}:")   # les stats changent
    await self._uow.commit()
```

Stratégie à **écrire** : quelles clés, quel TTL, invalidées par quels événements. Un cache
sans stratégie d'invalidation est un bug qui attend.

### Où

- **applicatif** : Redis (partagé entre instances), ou en mémoire (par instance —
  incohérent en multi-instance, OK pour du dev / des données vraiment locales).
- **HTTP** : en-têtes `Cache-Control`, `ETag`, `304 Not Modified` (le client / un CDN cache).
- **`taskman`** : `Cache` (`Protocol`) → `InMemoryCache` (dev/test) / `RedisCache` (prod),
  choisi selon `APP_REDIS_URL`.

---

## 5. Pagination : *offset* vs *cursor* (*keyset*)

### Offset (ce qu'on a) — simple, mais…

```sql
SELECT * FROM tasks ORDER BY id LIMIT 20 OFFSET 100000
```

La base **parcourt et jette** 100 000 lignes avant d'en renvoyer 20. `OFFSET` élevé = lent.
Et si une ligne est insérée entre deux pages, on **saute** ou **duplique** un élément.

### Cursor / keyset — rapide et stable

```sql
SELECT * FROM tasks WHERE (priority, id) < (:last_priority, :last_id)
ORDER BY priority DESC, id DESC LIMIT 20
```

On repart de **la dernière ligne vue** (le *cursor*), pas d'un numéro. La base utilise
l'**index** → temps constant quelle que soit la profondeur. Pas de saut/doublon.

Le *cursor* : un jeton **opaque** (base64 de `{priority, id}`) renvoyé dans la réponse.

```json
{ "items": [...], "next_cursor": "eyJwcmlvcml0eSI6MywiaWQiOjQyfQ==" }
```

- **inconvénient** : pas de « page 7 » ni de `total` bon marché (c'est un `COUNT` séparé).
- **quand** : listes potentiellement grandes, *scroll infini*, exports. Pour un back-office
  avec 200 lignes, l'offset suffit.

---

## 6. Le problème N+1 (rappel Module 04 + détection systématique)

```python
projects = await session.scalars(select(ProjectRow))      # 1 requête
for p in projects:
    print(len(p.tasks))                                     # +1 requête par projet !
```

### Détecter

- `echo=True` : compte les `SELECT` pour un endpoint de liste. `> 1 + 1` par ressource = N+1.
- un test qui compte : intercepter les requêtes via un *event listener* SQLAlchemy et
  `assert query_count <= 2`.

### Corriger

| Relation | Chargement | Requêtes |
|---|---|---|
| *-to-many* (les tâches d'un projet) | `selectinload(ProjectRow.tasks)` | 2 (une pour les projets, une `WHERE id IN (...)`) |
| *-to-one* (le projet d'une tâche) | `joinedload(TaskRow.project)` | 1 (`JOIN`) |
| juste **compter** les enfants | `func.count` + `GROUP BY` | 1 |

En async, un *lazy load* dans une boucle lève souvent `MissingGreenlet` → l'erreur t'oblige
à choisir explicitement.

---

## 7. Streaming : réponses qui ne tiennent pas en RAM

Exporter 500 000 tâches en JSON → 200 Mo en mémoire → OOM. On **streame** :

```python
from fastapi.responses import StreamingResponse

@router.get("/tasks/export")
async def export(service: TaskServiceDep) -> StreamingResponse:
    async def rows():
        async for task in service.iter_all():         # générateur async, une ligne à la fois
            yield task.model_dump_json() + "\n"        # NDJSON : un objet JSON par ligne
    return StreamingResponse(rows(), media_type="application/x-ndjson")
```

- **NDJSON** (*newline-delimited JSON*) : le client lit ligne par ligne, sans tout charger.
- la mémoire reste **constante** quelle que soit la taille.
- voir aussi *Server-Sent Events* (Module 12) pour du temps réel.

---

## 8. Autres leviers

- **index** : sur les colonnes de `WHERE` / `ORDER BY` / `JOIN`. `EXPLAIN ANALYZE` montre si
  la base fait un *seq scan* (mauvais) ou un *index scan*.
- **`select` ciblé** : ne charge pas 15 colonnes pour en afficher 3 (`select(TaskRow.id,
  TaskRow.title)`).
- **connexions** : dimensionne le pool (`pool_size`, `max_overflow`) selon
  `workers × pool_size ≤ max_connections` de PostgreSQL.
- **`gzip`** : `GZipMiddleware` compresse les grosses réponses JSON.
- **N requêtes → 1** : `WHERE id IN (...)` plutôt qu'une boucle.

---

## 9. Pièges fréquents

1. **Appel bloquant dans une route `async`** (le n°1) → toute la boucle gèle.
2. **`async def` partout par superstition** + code sync dedans → pire des deux mondes.
3. **`BackgroundTasks` pour une tâche critique** → perdue si le process meurt.
4. **Cache sans invalidation** → données périmées, bugs « fantômes ».
5. **`OFFSET 100000`** → scan complet ; utilise un *cursor*.
6. **N+1 non détecté** (jamais lancé avec `echo=True`).
7. **Tâche worker non idempotente** → *at-least-once* la rejoue → doublon (2 e-mails, 2 débits).
8. **Tout charger en mémoire pour exporter** → OOM ; streame.
9. **Optimiser sans mesurer** → tu accélères ce qui n'était pas le problème.
10. **Cache en mémoire en multi-instance** → chaque instance a un état différent.

---

## 10. Ce que `taskman` gagne

- `core/cache.py` : `Cache` (`Protocol`), `InMemoryCache` (TTL), `RedisCache` ; choisi via
  `APP_REDIS_URL` ;
- `GET /projects/{id}/stats` : agrégation coûteuse **mise en cache** (*cache-aside* +
  invalidation à la complétion / création / suppression de tâche) ;
- notification à la complétion : `BackgroundTasks` → puis tâche `taskiq` (broker Redis,
  `InMemoryBroker` en test), **idempotente** ;
- `GET /tasks` : pagination **cursor** (`next_cursor`) en plus de l'offset ;
- `GET /tasks/export` : NDJSON **streamé**, mémoire constante ;
- test qui **compte les requêtes SQL** (garde-fou anti-N+1) ;
- `GZipMiddleware`.

---

## 11. À savoir refaire sans aide

- Reconnaître un appel bloquant dans une coroutine et le corriger.
- Choisir entre `BackgroundTasks` et un worker, et rendre une tâche idempotente.
- Implémenter un cache *cache-aside* **avec** stratégie d'invalidation.
- Passer une liste d'offset à cursor et expliquer le gain.
- Détecter un N+1 (`echo`, compteur de requêtes) et le corriger (`selectinload`/`joinedload`/`count`).
- Streamer une grosse réponse en NDJSON.
- Mesurer **avant** d'optimiser.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
