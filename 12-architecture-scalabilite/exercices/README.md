# Module 12 — Exercices

**Filet :** `git commit -m "checkpoint: avant module 12"`.
**Nouvelle dep :** `sse-starlette`.

---

## Exercice 12.1 — Bounded contexts + `import-linter` 🔴

1. Réorganise `taskman/` par **bounded context** :
   ```
   taskman/
   ├── accounts/     (ex-auth : users, tokens, security)
   ├── projects/
   ├── tasks/
   └── shared/       (config, db, exceptions, observabilité, cache, realtime)
   ```
   Chaque module métier a un `public.py` qui **ré-exporte** ce que les autres ont le droit
   d'utiliser (schémas, service).
2. `tasks/` importe `projects.public` / `accounts.public`, **jamais**
   `projects.repositories.*`.
3. Ajoute `import-linter` (`.importlinter`) : contrat « `tasks` ne dépend pas des internes
   de `projects` » ; lance-le en CI.

**Critères d'acceptation**
- [ ] `lint-imports` passe et **échouerait** si `tasks/` importait un module interne de `projects/`.
- [ ] La suite de tests reste verte après la réorganisation.

> ⚠️ Gros refactor. Fais-le par petites étapes (un module à la fois), tests verts entre chaque.

---

## Exercice 12.2 — Outbox pattern 🔴

1. `OutboxRow` (`event_type`, `payload` JSON, `created_at`, `published_at` nullable).
2. `taskman/outbox.py` : `OutboxRepository` (`Protocol` : `add`, `list_unpublished`,
   `mark_published`) + impls SQL et mémoire + `drain_outbox(outbox, publisher, uow)`.
3. `taskman/domain/events.py` : `DomainEvent(type, payload)` (frozen).
4. `TaskService.complete` : `await outbox.add(DomainEvent("task.completed", {...}))` **avant**
   `commit` → tâche + événement atomiques.
5. Une tâche `taskiq` périodique (`drain_outbox_task`) qui draine toutes les N secondes.
6. Migration Alembic.

**Critères d'acceptation**
- [ ] Après un `POST /v1/tasks/{id}/complete`, une ligne `outbox` existe (`published_at IS NULL`).
- [ ] Si le `commit` échoue, **ni** la tâche **ni** l'événement ne sont écrits.
- [ ] `drain_outbox` publie puis marque ; un 2ᵉ appel ne republie rien.

---

## Exercice 12.3 — Idempotence des écritures 🔴

1. `IdempotencyMiddleware` : pour `POST`/`PATCH` **avec** l'en-tête `Idempotency-Key` :
   - clé de cache `idem:{méthode}:{chemin}:{clé}` ;
   - **rejeu** (clé connue) → renvoie la réponse stockée + en-tête `Idempotent-Replay: true`,
     sans exécuter la route ;
   - **1er appel** → exécute, capture la réponse (status 2xx, taille raisonnable), la stocke
     24 h.
2. Monte-le dans `create_app`.

**Critères d'acceptation**
- [ ] 2 `POST /v1/tasks` avec la **même** `Idempotency-Key` → **une** ressource, même réponse.
- [ ] Clés différentes → 2 ressources.
- [ ] Pas d'en-tête → pas de déduplication.
- [ ] Une réponse d'erreur (4xx/5xx) n'est **pas** mémorisée (le client peut re-tenter).

---

## Exercice 12.4 — Versionnage `/v1` + `/v2` 🟡

1. Monte **toute** l'API métier sous `/v1` (`APIRouter(prefix="/v1")` qui inclut auth,
   admin, projects, tasks). `oauth2_scheme` → `tokenUrl="v1/auth/login"`.
2. `/health`, `/ready`, `/metrics`, `/` **restent** non versionnés.
3. `taskman/api/routes/v2.py` : **un** endpoint `GET /v2/tasks/{id}` avec un contrat
   **modifié** (`checklist_total`/`checklist_done` au lieu de `checklist`, `overdue` au lieu
   de `is_overdue`), qui **réutilise** `TaskService`.
4. Adapte tous les tests (`/tasks` → `/v1/tasks`, etc.).

**Critères d'acceptation**
- [ ] `/v1/tasks/{id}` et `/v2/tasks/{id}` répondent, avec des contrats **différents**.
- [ ] `/tasks` (sans version) → 404.
- [ ] `/health` fonctionne toujours sans préfixe.

---

## Exercice 12.5 — Temps réel (SSE) 🔴

1. `taskman/realtime.py` : `InMemoryEventPublisher` (broadcast local via `asyncio.Queue`) +
   `RedisEventPublisher` (pub/sub) + `build_event_publisher(redis_url)`.
2. `TaskService.complete` : `await events.publish(event)` après commit (best-effort).
3. `GET /v1/events` (`sse-starlette` `EventSourceResponse`) : authentifié, envoie
   `{"event": "connected"}` immédiatement puis relaie chaque événement de `publisher.subscribe()` ;
   s'arrête si `request.is_disconnected()`.
4. `main.py` : `app.state.event_publisher = build_event_publisher(...)`, fermé dans le `lifespan`.

**Critères d'acceptation**
- [ ] Un client sur `GET /v1/events` reçoit `connected`, puis `task.completed` quand une
      autre requête complète une tâche.
- [ ] `Content-Type: text/event-stream`.
- [ ] Multi-instance : documenter que le fan-out passe par Redis pub/sub.

---

## Exercice 12.6 — ADR 🟢

`docs/adr/` : au moins 3 décisions (monolithe modulaire, outbox, versionnage), datées, au
format *contexte → décision → conséquences (positif/négatif) → alternatives écartées*.

**Critères d'acceptation**
- [ ] Chaque ADR a une section « conséquences négatives » **non vide**.
- [ ] Chaque ADR dit **quand** ré-ouvrir la décision.

---

## Exercice final — Refaire `taskman` de zéro 🏁

**2 jours, sans regarder.** Pas à l'identique — les *décisions* comptent. Cf.
[`../THEORIE.md`](../THEORIE.md) §10.

---

## Rendu

```bash
alembic upgrade head
ruff check . && ruff format --check . && mypy taskman && pytest -m "not e2e"
lint-imports
git add -A && git commit -m "feat(module-12): bounded contexts, outbox, Idempotency-Key, versionnage, SSE"
```

Puis [`../solutions/README.md`](../solutions/README.md) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).
