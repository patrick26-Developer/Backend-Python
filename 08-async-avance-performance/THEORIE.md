# Module 08 — Async avancé & performance

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

**Identifier un goulot d'étranglement et choisir la bonne parade.** `async` mal utilisé est
plus lent que du sync.

## Pages de doc FastAPI couvertes

Concurrency and `async` / `await` (approfondi) · Background Tasks · Stream JSON Lines ·
Server-Sent Events · Stream Data · Custom Response (Streaming/File) · Request Files (upload) ·
JSON with Bytes as Base64 (annexe) · Reference : `Background Tasks - BackgroundTasks`,
`Custom Response Classes`, `UploadFile class`.

## Plan

1. *Event loop* : ce qui la bloque (CPU, I/O sync), parades (`run_in_threadpool`, `to_thread`).
2. `BackgroundTasks` : usages, limites (même process, pas de reprise).
3. File de tâches : `taskiq` / `ARQ` / Celery — quand externaliser.
4. Cache Redis : *cache-aside*, clés, TTL, invalidation, `Cache-Control`.
5. Pagination : *offset* vs *keyset/cursor*, métadonnées.
6. DB : index, `selectinload`/`joinedload`, `EXPLAIN`, chasse au N+1.
7. Streaming : `StreamingResponse`, NDJSON, SSE.
8. Mesure : *load testing* (`locust`/`k6`), lecture d'un profil.

## Exercices (aperçu)

- Notification e-mail : route → `BackgroundTasks` → worker externe.
- Cache sur `GET /projects/{id}/stats` + stratégie d'invalidation écrite.
- Pagination *cursor* sur `GET /tasks`.
- Corriger un N+1 introduit volontairement ; prouver le gain par un test de charge.
- Export `GET /tasks/export` en NDJSON streamé.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md#module-08--async-avancé--performance-).
