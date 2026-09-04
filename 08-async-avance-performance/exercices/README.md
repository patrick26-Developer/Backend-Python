# Module 08 — Exercices

**Filet :** `git commit -m "checkpoint: avant module 08"`.
**Nouvelles deps :** `redis`, `taskiq`, `taskiq-redis` (`pip install -e ".[dev]"`).

---

## Exercice 08.1 — Repérer et corriger un blocage 🟡

1. Introduis **volontairement** un `time.sleep(0.5)` dans une route `async` de `taskman`.
2. Écris un test qui lance **10 requêtes concurrentes** (`asyncio.gather`) et mesure le temps
   total. Constate : ~5 s (séquentiel) au lieu de ~0,5 s.
3. Remplace par `await asyncio.sleep(0.5)` → le test repasse sous 1 s.
4. Retire le `sleep`. Retiens le réflexe : **aucun appel bloquant dans une coroutine**.

**Critères d'acceptation**
- [ ] Le test de concurrence montre la différence bloquant / non-bloquant.
- [ ] Tu sais citer 4 opérations bloquantes interdites et leur parade.

---

## Exercice 08.2 — Abstraction de cache 🟡

1. `taskman/core/cache.py` : `Cache` (`Protocol` : `get`, `set(*, ttl)`, `delete`,
   `delete_prefix`, `close`), `InMemoryCache` (dict + TTL via `time.monotonic`), `RedisCache`
   (`redis.asyncio`, `scan_iter` pour `delete_prefix`), `build_cache(redis_url)`.
2. `taskman/core/config.py` : `redis_url: str | None = None`.
3. `taskman/main.py` : `app.state.cache = build_cache(settings.redis_url)` dans le `lifespan`,
   `await cache.close()` à l'arrêt.
4. `api/deps.py` : `get_cache(request)` → `request.app.state.cache` ; `CacheDep`.

**Critères d'acceptation**
- [ ] `InMemoryCache` respecte le TTL (une clé expirée renvoie `None`).
- [ ] `delete_prefix("project:7:")` supprime `project:7:stats` mais pas `project:8:stats`.
- [ ] Sans `APP_REDIS_URL`, `build_cache(None)` renvoie un `InMemoryCache`.

---

## Exercice 08.3 — `GET /projects/{id}/stats` (cache-aside + invalidation) 🔴

1. `schemas` : `TaskStats` (`project_id`, `total`, `by_status: dict[str,int]`, `overdue`,
   `completion_rate: float`).
2. `TaskRepository.project_stats(project_id) -> tuple[dict[str,int], int]` : agrégation
   **SQL** (`GROUP BY status` + un `COUNT` pour les retards). Impls SQL et mémoire.
3. `TaskService` reçoit un `cache: Cache`. `stats(project_id)` :
   - lit `project:{id}:stats` dans le cache → si présent, `TaskStats.model_validate_json` ;
   - sinon calcule, `cache.set(..., ttl=60)`, renvoie.
4. **Invalidation** : `create`, `update`, `complete`, `delete` appellent
   `cache.delete(f"project:{pid}:stats")`.
5. Route `GET /projects/{id}/stats` : `ProjectService.get` d'abord (404 + propriété), puis
   `TaskService.stats`.

**Critères d'acceptation**
- [ ] 2 appels consécutifs à `stats` → le 2ᵉ ne relance **pas** les requêtes SQL (vérifie
      via un compteur ou `db_echo`).
- [ ] Créer une tâche dans le projet → l'appel `stats` suivant renvoie le **nouveau** total.
- [ ] `project_stats` est **1** requête `GROUP BY` + 1 `COUNT`, pas N.
- [ ] `GET /projects/999/stats` → 404.

---

## Exercice 08.4 — Pagination *cursor* 🔴

1. `TaskFilters` : `cursor: str | None`. `TaskPage` : `next_cursor: str | None`.
2. `TaskRepository.list_keyset(*, owner_id, limit, after: tuple[datetime,int] | None)` :
   `WHERE (created_at, id) < :after ORDER BY created_at DESC, id DESC LIMIT :limit`.
3. `TaskService.list` :
   - `cursor` fourni → décode (`base64(json({c, i}))`), `list_keyset` ;
   - sinon si `sort == "-created_at"` et `offset == 0` → `list_keyset(after=None)` ;
   - sinon → l'ancien `list` offset.
   - `next_cursor` = encode `(dernier.created_at, dernier.id)` **si** `len(rows) == limit`.
4. Un `cursor` illisible → `BadRequestError` (400).

**Critères d'acceptation**
- [ ] Parcourir toutes les pages via `next_cursor` visite **chaque** tâche **une** fois
      (aucun saut, aucun doublon), même si on insère une tâche entre deux pages.
- [ ] `GET /tasks?cursor=xxx-invalide` → 400 `bad_request`.
- [ ] Le mode offset (`sort=-priority`) fonctionne toujours.

---

## Exercice 08.5 — Export NDJSON streamé 🟡

1. `TaskRepository.iter_by_owner(owner_id) -> AsyncIterator[TaskRead]` :
   `session.stream_scalars(...)` (curseur serveur).
2. `TaskService.export()` : `async for` sur le repo, `yield` chaque tâche.
3. Route `GET /tasks/export` → `StreamingResponse` d'un générateur qui `yield` chaque tâche
   en `model_dump_json() + "\n"`, `media_type="application/x-ndjson"`.
4. **Attention à l'ordre des routes** : `/tasks/export` **avant** `/tasks/{task_id}`.

**Critères d'acceptation**
- [ ] `GET /tasks/export` renvoie une ligne JSON par tâche, `Content-Type` NDJSON.
- [ ] Un `member` n'exporte que **ses** tâches.
- [ ] La mémoire n'augmente pas avec le nombre de tâches (curseur serveur, pas `.all()`).

---

## Exercice 08.6 — Tâche de fond & worker 🔴

1. `taskman/services/notifications.py` : `Notifier` (`Protocol`) + `LoggingNotifier`.
2. `POST /tasks/{id}/complete` : injecte `BackgroundTasks` + `NotifierDep`, fait
   `background.add_task(notifier.task_completed, task)` **après** avoir formé la réponse.
3. Test : `monkeypatch` `LoggingNotifier.task_completed`, vérifie qu'il est appelé avec la
   bonne tâche **après** la réponse.
4. `taskman/tasks.py` : `broker` taskiq (`InMemoryBroker` sans Redis, `ListQueueBroker`
   sinon) + `@broker.task notify_task_completed(task_id, email)` **idempotente**.
   `taskman/worker.py` : `from taskman.tasks import broker`.
5. **Bonus** : migre le `/complete` vers `await notify_task_completed.kiq(...)` et fais
   tourner `taskiq worker taskman.worker:broker` (nécessite Redis).

**Critères d'acceptation**
- [ ] La notification s'exécute **après** l'envoi de la réponse (le client n'attend pas).
- [ ] `notify_task_completed` peut s'exécuter 2 fois sans effet de bord (idempotence).
- [ ] `taskiq worker taskman.worker:broker` démarre (si Redis dispo).

---

## Exercice 08.7 — Garde-fou anti-N+1 🟡

1. Écris un helper de test qui **compte les requêtes SQL** (event listener SQLAlchemy
   `before_cursor_execute`).
2. Teste : `GET /projects` avec 10 projets → **≤ 3** requêtes (pas 1 + 10).
3. Introduis un N+1 (charge `p.tasks` dans une boucle), vérifie que le test **échoue**,
   puis corrige.

**Critères d'acceptation**
- [ ] Le test compte les requêtes et pose une borne.
- [ ] Un N+1 introduit fait échouer le test.

---

## Rendu

```bash
alembic upgrade head          # (pas de nouvelle migration ce module)
ruff check . && ruff format --check . && mypy taskman && pytest -m "not e2e"
git add -A && git commit -m "feat(module-08): cache + invalidation, pagination cursor, export NDJSON, tâches de fond"
```

Puis [`../solutions/README.md`](../solutions/README.md) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

**Mini-projet associé** : [`shorturl`](../../projets/checkpoints/shorturl/BRIEF.md) — ajoute-lui
un cache de résolution + un compteur de clics asynchrone.
