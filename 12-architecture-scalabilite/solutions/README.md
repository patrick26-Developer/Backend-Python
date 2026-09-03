# Module 12 — Solutions : les choix de conception

> Snapshot `taskman` v0.12.0 — l'état **final** du projet. Ligne par ligne :
> [`../PAS-A-PAS.md`](../PAS-A-PAS.md). Théorie : [`../THEORIE.md`](../THEORIE.md).

```bash
uv run ruff check . && uv run mypy taskman && uv run pytest -q      # tout vert
uv run uvicorn taskman.main:app --reload                            # /v1/docs et /v2/docs
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/events   # flux SSE
```

---

## Décisions

### 1. Outbox : l'événement est une ligne, écrite dans la transaction

`TaskService.complete` écrit la tâche **et** `OutboxRow` dans **une** transaction
(`_uow.commit()` unique). Impossible de committer la tâche sans l'événement, ou l'inverse.
Un worker (`drain_outbox`) publie ensuite les lignes en attente vers le broker et les marque
`published_at`. Garantie **at-least-once** → les consommateurs doivent être **idempotents**.

Le double-write naïf (`repo.save()` puis `broker.publish()`) perd des événements dès que le
broker est indisponible une milliseconde. L'outbox transforme « deux systèmes, pas de
transaction » en « un seul système, une transaction ».

### 2. SSE best-effort *en plus* de l'outbox

`complete` fait aussi `_events.publish(event)` **après** le commit, pour pousser
l'événement aux clients SSE **immédiatement**. Si ça échoue : l'outbox rattrapera. L'outbox
est la source de vérité ; le SSE est le confort temps réel.

### 3. Fan-out : une `asyncio.Queue` par connexion

`InMemoryEventPublisher` tient un `set` de queues (une par abonné SSE). `publish` fait
`put_nowait` dans toutes. `maxsize=100` : on **perd** un événement pour un client lent
plutôt que bloquer les autres. Mono-process. `RedisEventPublisher` (pub/sub sur
`taskman:events`) fait le même contrat en **multi-instance** : chaque instance relaie à
**ses** clients — c'est la seule version correcte derrière un load-balancer.

### 4. Versionnage par URI : `/v1` métier, infra hors version

Tout le métier est sous `APIRouter(prefix="/v1")`. `/health`, `/ready`, `/metrics`, `/` ne
sont **pas** versionnés (ce sont des contrats d'exploitation, pas d'API publique). `/v2`
coexiste : `v2.py` **réutilise `TaskService`** — seul le **schéma de sortie** change
(`overdue` au lieu de `is_overdue`, `checklist_total`/`checklist_done` au lieu de la liste).
On ne duplique jamais la logique métier pour une nouvelle version.

### 5. `Location` via `request.url_for(...).path`, pas de chaîne codée en dur

Avec un `prefix="/v1"` sur un routeur parent, `response.headers["Location"] = f"/tasks/{id}"`
serait **faux**. `request.url_for("get_task", task_id=id).path` résout le chemin réel
(`/v1/tasks/{id}`, `root_path` compris).

### 6. Idempotency-Key : middleware ASGI, rejeu sans exécuter la route

`IdempotencyMiddleware` n'agit que sur `POST`/`PATCH` **avec** l'en-tête. Au 1ᵉʳ appel il
capture la réponse (via un `send` wrapper) et la met en cache 24 h **si 2xx**. Au rejeu, la
route **n'est pas appelée** : on renvoie la réponse d'origine octet pour octet +
`Idempotent-Replay: true`. Une erreur n'est jamais mémorisée (elle doit rester re-tentable).

### 7. `TaskService` à 6 dépendances : le smell est documenté

`(tasks, uow, actor, cache, outbox, events)` → signe qu'on gagnerait à séparer commandes et
requêtes (**CQRS léger**). Laissé en un service pour garder un point d'entrée unique ;
l'exercice 12.1 fait la découpe. Reconnaître la dette et la nommer fait partie du métier.

### 8. Le schéma final

3 migrations, squashées jusqu'à `fb04f2615d4f` puis `0f145551658f` (task.completed_at) et
`17504d0dcfdd` (outbox). `render_as_batch=True` + `MetaData(naming_convention=...)` : les
migrations SQLite nomment leurs contraintes, donc `alembic upgrade` fonctionne aussi bien
sur SQLite (dev) que PostgreSQL (prod).

---

## L'examen

`taskman` est fini. Le vrai test du module : **refais-le de zéro, en 2 jours, sans copier**
(cahier des charges dans [`../THEORIE.md`](../THEORIE.md) §10). Si tu bloques sur une brique,
c'est le module correspondant qu'il faut relire — pas cette solution.
