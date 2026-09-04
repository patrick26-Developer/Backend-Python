# Module 08 — Solutions : les choix de conception

> Snapshot `taskman` v0.8.0 dans `taskman/` + `tests/`. Explication
> ligne par ligne : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
# depuis la racine :
pytest -m "not e2e"
mypy taskman
# avec un vrai Redis :
APP_REDIS_URL=redis://localhost:6379/0 fastapi dev taskman/main.py
APP_REDIS_URL=redis://localhost:6379/0 taskiq worker taskman.worker:broker
```

---

## Décisions

### 1. `Cache` est un `Protocol` — le service ignore Redis

`InMemoryCache` (dev/test) et `RedisCache` (prod) satisfont la même interface. Le
`TaskService` reçoit un `Cache`, jamais un client Redis. `build_cache(redis_url)` choisit à
l'exécution : sans `APP_REDIS_URL` → mémoire.

### 2. Cache-aside **+ invalidation active**, pas juste un TTL

TTL 60 s **et** suppression de la clé `project:{id}:stats` à chaque `create`/`update`/
`complete`/`delete` d'une tâche du projet. Un TTL seul afficherait des stats fausses jusqu'à
une minute. La stratégie est **écrite** (une clé par projet, 4 événements d'invalidation).

### 3. `project_stats` = **2 requêtes** (`GROUP BY` + `COUNT`), pas N

Compter par statut en Python sur toutes les tâches serait un N+1 déguisé. `GROUP BY status`
fait le travail dans la base.

### 4. Pagination *cursor* : keyset sur `(created_at, id)`

`WHERE (created_at, id) < (:last)` + `ORDER BY created_at DESC, id DESC`. Avec un index, la
base saute à la bonne position → temps **constant** (vs `OFFSET 100000` qui scanne). Pas de
saut/doublon si une ligne est insérée entre deux pages. Le mode *offset* reste disponible
pour les tris arbitraires.

### 5. Le *cursor* est **opaque**

`base64(json({created_at, id}))`. Le client le renvoie tel quel, ne le fabrique pas. Un
token illisible → `BadRequestError` (400), pas un 500.

### 6. Export : `StreamingResponse` + curseur serveur

`session.stream_scalars` (curseur côté base) + générateur async → mémoire **constante**
quel que soit le nombre de tâches. NDJSON (un JSON par ligne). Route `/tasks/export`
déclarée **avant** `/tasks/{task_id}` (sinon 422).

### 7. Notification : `BackgroundTasks` (livré) + `taskiq` (documenté)

Le `/complete` livré utilise `BackgroundTasks` — c'est *suffisant* pour une notification non
critique (rapide, best-effort). `taskman/tasks.py` + `worker.py` fournissent la version
**scale-out** (broker Redis, workers séparés, retries) pour quand ça ne suffit plus — l'exo
08.6 demande la migration.

### 8. `taskiq` : `InMemoryBroker` par défaut

Sans Redis, le broker exécute les tâches dans le process → aucune infra requise en dev/test.
`is_worker_process` évite de démarrer le broker deux fois (API + `taskiq worker`).

### 9. `GZipMiddleware`

Compresse les réponses > 1 Kio. Ajouté **avant** `RequestContextMiddleware` (donc plus
interne) : GZip compresse le corps, RequestContext ajoute l'entête `x-request-id` par-dessus.

### 10. Le renommage `list` → `list_page`

La méthode `list` d'un repository **masque le type `list`** dans la portée de la classe :
`list_keyset(...) -> list[TaskRead]` faisait échouer mypy (`list` = la méthode). On a
renommé la pagination offset en `list_page` ; `list_keyset` garde son nom.

---

## Grille d'auto-évaluation

- [ ] Ton service dépend-il de `Cache` (✅) ou d'un client Redis concret (❌) ?
- [ ] Une écriture invalide-t-elle le cache des stats du projet ?
- [ ] `project_stats` fait-il 2 requêtes ou une boucle Python ?
- [ ] Parcourir toutes les pages *cursor* visite chaque tâche exactement une fois ?
- [ ] Un `cursor` invalide → 400 (pas 500) ?
- [ ] `GET /tasks/export` garde-t-il une mémoire constante (curseur serveur) ?
- [ ] La notification s'exécute-t-elle **après** la réponse ?

➡️ [Module 09 — Observabilité & prod-readiness](../../09-observabilite-prod-readiness/THEORIE.md)
