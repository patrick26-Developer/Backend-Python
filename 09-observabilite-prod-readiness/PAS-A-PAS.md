# Module 09 — Explication pas à pas

> Nouveaux : `observability/{metrics,tracing}.py`, `api/routes/ops.py`. Modifiés :
> `api/routes/meta.py` (— `/health`), `core/config.py`, `main.py`.

---

## 1. `taskman/observability/metrics.py`

```python
REQUESTS = Counter("http_requests_total", "…", ["method", "path", "status"])
LATENCY  = Histogram("http_request_duration_seconds", "…", ["method", "path"],
                     buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0))
```

- **Counter** : `http_requests_total` — ne fait qu'augmenter. Prometheus calcule le *rate*
  (dérivée) au moment de la requête. Le label `status` permet de filtrer les 5xx (**E**rrors).
- **Histogram** : `http_request_duration_seconds` — chaque `.observe(v)` incrémente le
  *bucket* qui contient `v`, plus `_sum` et `_count`. Prometheus en déduit p50/p95/p99.
- les *buckets* sont **en secondes** et couvrent 5 ms → 5 s (adapte à ta latence réelle).

```python
def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)
```

**LE point critique.** `request.url.path` = `/tasks/42` → une série Prometheus **par
identifiant** → des millions de séries → Prometheus tombe. `request.scope["route"].path` =
`/tasks/{task_id}` (le **pattern**) → une seule série. C'est la **cardinalité bornée**.

```python
class MetricsMiddleware:
    async def __call__(self, scope, receive, send):
        ...
        start = time.perf_counter()
        status_code = 500
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = _route_template(request)
            REQUESTS.labels(request.method, path, str(status_code)).inc()
            LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
```

Même patron ASGI pur qu'au Module 05 : on intercepte `http.response.start` pour le statut,
on mesure dans un `finally` (même sur exception → `status_code` reste 500).

```python
def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

`generate_latest()` sérialise **tout** le registre Prometheus au format texte. Une ligne par
série. C'est ce que le serveur Prometheus *scrape*.

---

## 2. `taskman/api/routes/ops.py`

```python
@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

**Liveness** : 200 tant que le process tourne. **Ne vérifie rien d'autre.** Si `/health`
testait la DB, un incident DB ferait redémarrer le pod en boucle (il ne peut pas démarrer
non plus).

```python
@router.get("/ready")
async def ready(session: SessionDep, cache: CacheDep) -> JSONResponse:
    checks = {}
    try:
        await session.execute(text("SELECT 1")); checks["database"] = "ok"
    except Exception:
        checks["database"] = "fail"
    try:
        await cache.set("_readiness_probe", "1", ttl=5); checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "fail"
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if healthy else "degraded", "checks": checks},
                        status_code=200 if healthy else 503)
```

**Readiness** : « puis-je servir du trafic *maintenant* ? » Vérifie les dépendances
**critiques**. `503` → l'orchestrateur **retire** le pod du load-balancer (sans le tuer) ;
il y revient quand `/ready` repasse à 200.

- `text("SELECT 1")` : la requête la plus légère possible.
- `except Exception:` **volontairement large** : n'importe quelle panne (timeout, connexion
  refusée, auth) doit donner `"fail"`, pas une 500.
- le corps liste **chaque** check → l'astreinte voit *quoi* est cassé.

```python
@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()
```

`include_in_schema=False` : `/metrics` n'apparaît pas dans `/docs` ni `openapi.json` — c'est
une interface machine, pas une route d'API.

> **Auth** : les 3 routes `ops` sont **non authentifiées** — Prometheus et Kubernetes
> doivent y accéder. Mais on ne les expose **pas** publiquement (réseau interne, ou un proxy
> qui bloque `/metrics` de l'extérieur).

---

## 3. `taskman/observability/tracing.py`

```python
_configured = False

def configure_tracing(*, enabled, endpoint, service_name):
    global _configured
    if not enabled or _configured:
        return
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces") if endpoint else ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
```

- **imports paresseux** (`from opentelemetry... import` *dans* la fonction) : si
  `otel_enabled=false`, OTel n'est **jamais** importé au *runtime* → zéro surcoût.
- `TracerProvider` + `Resource(SERVICE_NAME=...)` : tous les spans porteront le nom du
  service (pour distinguer `taskman-api` de `taskman-worker` dans Jaeger).
- `BatchSpanProcessor` : bufferise et envoie les spans par lots (perf).
- `ConsoleSpanExporter` (dev) : les spans s'affichent dans le terminal.
  `OTLPSpanExporter` (prod) : vers un *collector* (Jaeger, Tempo, Datadog).
- `_configured` : idempotent — appelé une fois.

```python
def instrument_app(app):
    if not _configured: return
    FastAPIInstrumentor.instrument_app(app)   # un span par requête HTTP

def instrument_engine(sync_engine):
    if not _configured: return
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)   # un span par requête SQL
```

**Auto-instrumentation** : ces paquets patchent FastAPI et SQLAlchemy pour créer les spans
**sans toucher au code métier**. Une requête `GET /tasks/{id}` produit un span parent
(HTTP) et des spans enfants (chaque `SELECT`).

---

## 4. `taskman/main.py`

```python
def create_app(settings=None):
    ...
    configure_logging(...)
    tracing.configure_tracing(enabled=settings.otel_enabled, endpoint=settings.otel_endpoint,
                              service_name=settings.name)
    app = FastAPI(...)
    ...
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(MetricsMiddleware)          # <- mesure TOUTES les requêtes
    app.add_middleware(RequestContextMiddleware)   # <- le plus externe (request_id d'abord)
    register_error_handlers(app)
    tracing.instrument_app(app)
    app.include_router(ops.router)                 # /health, /ready, /metrics
    ...
```

Ordre des middlewares (`add_middleware` ajoute à l'**extérieur**) : de l'intérieur vers
l'extérieur = GZip → Metrics → RequestContext. `RequestContext` voit la requête en premier
(pose le `request_id`), `Metrics` mesure la durée *hors* sérialisation GZip.

```python
@asynccontextmanager
async def lifespan(app):
    engine = create_engine(...)
    ...
    tracing.instrument_engine(engine.sync_engine)   # spans SQL (si tracing actif)
    ...
    try:
        yield
    finally:
        # arrêt gracieux : Uvicorn a déjà attendu les requêtes en vol ;
        # ici on ferme les ressources.
        await broker.shutdown()
        await app.state.cache.close()
        await engine.dispose()
```

`engine.sync_engine` : `SQLAlchemyInstrumentor` s'attache au moteur **synchrone** sous-jacent
(l'async l'enveloppe).

---

## 5. Les tests

```python
async def test_ready_503_when_database_down(app):
    class BrokenSession:
        async def execute(self, *_a, **_k):
            raise RuntimeError("db down")
    app.dependency_overrides[get_session] = lambda: _yield(BrokenSession())
    ...
    assert resp.status_code == 503
    assert resp.json()["checks"]["database"] == "fail"
```

On **injecte une panne** : une session dont `execute` lève → `/ready` doit renvoyer 503 avec
`database: fail`, sans crash.

```python
async def test_metrics_path_label_is_route_template(member_client):
    ... GET /tasks/{tid} ...
    metrics = (await member_client.get("/metrics")).text
    assert 'path="/tasks/{task_id}"' in metrics      # le PATTERN
    assert f'path="/tasks/{tid}"' not in metrics     # PAS l'URL concrète
```

Le test qui **garde la cardinalité bornée** : si quelqu'un remet `request.url.path`, il
échoue.

---

## Ce qui vient au Module 10

Le Module 09 a ajouté des surfaces (`/metrics`, `/ready`). Le Module 10 les **durcit** avec
le reste : rate limiting, en-têtes de sécurité, CORS strict, audit OWASP API Top 10 — et
vérifie que `/metrics` n'est **pas** joignable de l'extérieur.
