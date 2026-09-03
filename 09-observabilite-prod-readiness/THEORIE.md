# Module 09 — Observabilité & prod-readiness

> **Objectif** : rendre `taskman` **exploitable par une équipe d'astreinte**. Métriques,
> traces, health checks (`/health` ≠ `/ready`), config 12-factor, arrêt gracieux.
> « Ça marche chez moi » n'est pas un critère de prod : on doit **voir** le système.
>
> **Durée estimée** : 8 à 11 h.
> **Pré-requis** : Modules 05 (logs) et 08 (cache, workers).

---

## 1. Les trois piliers

| Pilier | Répond à | Forme | Dans `taskman` |
|---|---|---|---|
| **Logs** | « Que s'est-il passé pour *cette* requête ? » | événements datés, corrélés | Module 05 (JSON + `request_id`) |
| **Métriques** | « Le système va-t-il bien, *globalement* ? » | séries temporelles numériques | Module 09 : Prometheus |
| **Traces** | « Où le temps est-il passé dans *cette* requête, à travers les services ? » | arbre de *spans* | Module 09 : OpenTelemetry |

Les trois se **corrèlent** : une métrique montre un pic de latence → une trace montre *quel*
appel est lent → les logs de ce `request_id` montrent *pourquoi*.

---

## 2. Métriques : Prometheus & la méthode **RED**

Pour **chaque** endpoint, on veut :

- **R**ate — requêtes par seconde ;
- **E**rrors — proportion de 5xx ;
- **D**uration — distribution de la latence (p50, p95, p99).

### Les types de métriques

| Type | Usage | Exemple |
|---|---|---|
| **Counter** | valeur qui ne fait qu'augmenter | `http_requests_total` |
| **Gauge** | valeur qui monte et descend | `db_connections_active` |
| **Histogram** | distribution (buckets) → quantiles | `http_request_duration_seconds` |
| **Summary** | quantiles calculés côté client | (rare, préfère l'histogram) |

### Middleware de métriques

```python
REQUESTS = Counter("http_requests_total", "…", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "…", ["method", "path"])

class MetricsMiddleware:
    async def __call__(self, scope, receive, send):
        ...
        start = time.perf_counter()
        # (capture le status via un send_wrapper, comme au Module 05)
        REQUESTS.labels(method, path, status).inc()
        LATENCY.labels(method, path).observe(time.perf_counter() - start)
```

⚠️ **Cardinalité** : `path` doit être le **template** (`/tasks/{task_id}`), **jamais** l'URL
concrète (`/tasks/42`, `/tasks/43`…) — sinon une série par id → explosion mémoire de
Prometheus. Récupère `request.scope["route"].path` (le pattern), pas `request.url.path`.

### L'endpoint `/metrics`

```python
@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

Prometheus le *scrape* toutes les N secondes. Format texte, une ligne par série. En général
**non authentifié** mais **non exposé publiquement** (réseau interne / derrière un proxy).

---

## 3. Traces : OpenTelemetry

Une **trace** suit une requête à travers les composants ; chaque étape est un **span**
(nom, début, durée, attributs, parent).

```
trace abc123
├─ span: GET /tasks/{id}                    12 ms
│  ├─ span: TaskService.get                 11 ms
│  │  ├─ span: SELECT tasks WHERE id=…       3 ms
│  │  └─ span: SELECT owner_id …             2 ms
```

### Instrumentation

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

FastAPIInstrumentor.instrument_app(app)          # un span par requête HTTP
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)   # un span par requête SQL
```

- **auto-instrumentation** : FastAPI, SQLAlchemy, httpx, redis ont des paquets
  `opentelemetry-instrumentation-*` qui créent les spans sans toucher ton code.
- **exporter** : où partent les traces — `ConsoleSpanExporter` (dev), OTLP vers un
  *collector* (Jaeger, Tempo, Datadog) en prod, via `OTEL_EXPORTER_OTLP_ENDPOINT`.
- **propagation** : le `traceparent` (en-tête W3C) relie les traces **entre services** (API
  → worker).

### Corréler trace ↔ logs

Injecter `trace_id` dans chaque log (via le `ContextVar` du Module 05, ou le
`LoggingInstrumentor` d'OTel). Un incident : métrique → trace → `trace_id` → tous les logs.

---

## 4. Health checks : `/health` ≠ `/ready`

**LE** piège classique : un seul `/health` qui vérifie la DB → au moindre hoquet DB,
l'orchestrateur **tue et redémarre** le pod (qui ne peut pas démarrer non plus) → boucle de
crash.

| Endpoint | Question | Vérifie | Échec ⇒ |
|---|---|---|---|
| **`/health`** (*liveness*) | « le process est-il vivant ? » | **rien** (ou juste que l'event loop répond) | l'orchestrateur **redémarre** le pod |
| **`/ready`** (*readiness*) | « peut-il servir du trafic *maintenant* ? » | DB, cache, dépendances critiques | l'orchestrateur **retire** le pod du load-balancer (sans le tuer) |

```python
@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}          # 200 tant que le process tourne

@router.get("/ready")
async def ready(session: SessionDep, cache: CacheDep) -> JSONResponse:
    checks = {}
    try:
        await session.execute(text("SELECT 1")); checks["db"] = "ok"
    except Exception: checks["db"] = "fail"
    try:
        await cache.set("_probe", "1", ttl=5); checks["cache"] = "ok"
    except Exception: checks["cache"] = "fail"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "degraded", "checks": checks},
                        status_code=200 if ok else 503)
```

- `/ready` → **503** si une dépendance critique est down. Le pod reste vivant, sort du LB,
  y revient quand tout va bien.
- garde les checks **rapides** (timeout court) — `/ready` est appelé souvent.

### `/startup` (optionnel)

Certaines plateformes distinguent une 3ᵉ sonde : « le démarrage (migrations, chargement de
modèle) est-il fini ? » — pour ne pas tuer un pod lent à démarrer.

---

## 5. Config 12-factor (finalisation)

Les [12 facteurs](https://12factor.net) pertinents ici :

- **III. Config** : tout par variable d'environnement (`pydantic-settings`, Module 03).
  **Un** artefact (image Docker) pour tous les environnements.
- **IV. Backing services** : DB, Redis, e-mail = des ressources attachées, remplaçables par
  une URL. `taskman` : `APP_DATABASE_URL`, `APP_REDIS_URL`.
- **XI. Logs** : l'app écrit sur `stdout`, **ne gère pas** de fichiers ni de rotation —
  c'est l'orchestrateur qui collecte (Module 05).
- **IX. Disposability** : démarrage rapide, **arrêt gracieux**.

### Arrêt gracieux

```
SIGTERM reçu
  ├─ arrêter d'accepter de nouvelles requêtes
  ├─ laisser finir les requêtes en cours (timeout, ex. 30 s)
  ├─ fermer le pool DB, le broker, le cache   (le `lifespan` s'en charge)
  └─ sortir
```

Uvicorn gère `SIGTERM`/`SIGINT` : il arrête l'accept, attend les requêtes en vol
(`--timeout-graceful-shutdown`), puis déclenche le *shutdown* du `lifespan`. Ton `finally:`
du `lifespan` (Module 04/08) **doit** fermer proprement les ressources.

---

## 6. Alerting (survol)

Les métriques ne servent que si quelqu'un est prévenu. Règles typiques (Prometheus
Alertmanager) :

- taux de 5xx > 1 % sur 5 min ;
- p99 de latence > 1 s sur 10 min ;
- `/ready` down > 2 min ;
- file de tâches (`taskiq`) qui s'allonge ;
- pool DB saturé.

Une bonne alerte est **actionnable** (dit quoi regarder) et **rare** (sinon on l'ignore).

---

## 7. Tableaux de bord

Un dashboard Grafana par service, avec au minimum : RED par endpoint, erreurs récentes
(lien vers les logs), latence DB, taille de la file de tâches, saturation (CPU, mémoire,
connexions). `taskman` fournit un `grafana-dashboard.json` d'exemple.

---

## 8. Pièges fréquents

1. **Un seul `/health` qui teste la DB** → boucle de crash au moindre incident DB.
2. **`path` = URL concrète** dans les labels de métriques → explosion de cardinalité.
3. **`/ready` lent** (checks sans timeout) → il devient lui-même le problème.
4. **Logguer ET tracer la même chose 3 fois** → bruit, coût.
5. **Pas de corrélation** trace ↔ logs (`trace_id` absent des logs).
6. **Métriques derrière l'authentification** → Prometheus ne peut pas scraper.
7. **Exposer `/metrics` publiquement** → fuite d'infos (noms d'endpoints, volumétrie).
8. **`lifespan` qui ne ferme rien** → connexions qui fuient à chaque redéploiement.
9. **Alertes trop nombreuses** → fatigue d'alerte, on rate la vraie.
10. **Instrumenter en dev seulement** → en prod, tu es aveugle.

---

## 9. Ce que `taskman` gagne

- `observability/metrics.py` : middleware RED + `/metrics` (Prometheus), `path` = template ;
- `observability/tracing.py` : `configure_tracing()` (OTel, exporter console en dev, OTLP
  sinon), auto-instrumentation FastAPI + SQLAlchemy, `trace_id` dans les logs ;
- routes `/health` (liveness, inchangée) et `/ready` (vérifie DB + cache → 503 si down) ;
- `Settings` : `otel_enabled`, `otel_endpoint` ; arrêt gracieux vérifié ;
- tests : `/ready` renvoie 503 quand la DB est coupée ; `/metrics` expose les séries ;
  cardinalité du `path` bornée.

---

## 10. À savoir refaire sans aide

- Distinguer liveness et readiness, et implémenter les deux correctement.
- Exposer des métriques RED avec des labels à **cardinalité bornée**.
- Brancher l'auto-instrumentation OpenTelemetry et corréler trace ↔ logs.
- Garantir un arrêt gracieux (fermeture des ressources dans le `lifespan`).
- Écrire une alerte actionnable.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
