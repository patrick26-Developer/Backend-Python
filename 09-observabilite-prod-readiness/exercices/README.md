# Module 09 — Exercices

**Filet :** `git commit -m "checkpoint: avant module 09"`.
**Nouvelles deps :** `prometheus-client`, `opentelemetry-*` (`pip install -e ".[dev]"`).

---

## Exercice 09.1 — Métriques RED 🔴

1. `taskman/observability/metrics.py` :
   - `REQUESTS = Counter("http_requests_total", …, ["method", "path", "status"])` ;
   - `LATENCY = Histogram("http_request_duration_seconds", …, ["method", "path"],
     buckets=(...))` ;
   - `MetricsMiddleware` (ASGI pur) : capture méthode, **template de route**, statut, durée ;
     `REQUESTS.labels(...).inc()` et `LATENCY.labels(...).observe(...)` dans un `finally`.
   - `metrics_response()` : `Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)`.
2. `_route_template(request)` : `request.scope.get("route").path` (`/tasks/{task_id}`),
   **pas** `request.url.path` (`/tasks/42`).
3. `main.py` : `app.add_middleware(MetricsMiddleware)`.

**Critères d'acceptation**
- [ ] Après une requête sur `/tasks/{id}`, `/metrics` contient une série avec
      `path="/tasks/{task_id}"` — et **pas** `path="/tasks/42"`.
- [ ] `http_request_duration_seconds` a des *buckets* et un `_count` / `_sum`.
- [ ] `/metrics` n'est **pas** dans `openapi.json` (`include_in_schema=False`).

---

## Exercice 09.2 — `/health` vs `/ready` 🔴

1. `taskman/api/routes/ops.py` :
   - `GET /health` → `{"status": "ok"}`, **toujours 200** (liveness).
   - `GET /ready` → vérifie la DB (`SELECT 1`) **et** le cache (`cache.set` d'une sonde) ;
     renvoie `{"status": "ready"|"degraded", "checks": {...}}` avec **200** si tout va bien,
     **503** sinon.
   - `GET /metrics` → `metrics_response()`, `include_in_schema=False`.
2. Retire `/health` de `meta.py` (il déménage dans `ops.py`).
3. `main.py` : `app.include_router(ops.router)`.

**Critères d'acceptation**
- [ ] `/health` → 200 même si la DB est coupée.
- [ ] `/ready` → **503** quand la DB est injoignable (teste avec une session qui lève sur
      `execute`).
- [ ] `/ready` reste rapide (pas de check sans timeout).
- [ ] Les 3 routes `ops` sont accessibles **sans** authentification.

---

## Exercice 09.3 — Traçage OpenTelemetry 🔴

1. `taskman/observability/tracing.py` :
   - `configure_tracing(*, enabled, endpoint, service_name)` : si `enabled`, crée un
     `TracerProvider` avec `Resource(SERVICE_NAME=service_name)`, un `BatchSpanProcessor` +
     `ConsoleSpanExporter` (sans endpoint) ou `OTLPSpanExporter` (avec).
   - `instrument_app(app)` : `FastAPIInstrumentor.instrument_app(app)` (si configuré).
   - `instrument_engine(sync_engine)` : `SQLAlchemyInstrumentor().instrument(engine=...)`.
2. `taskman/core/config.py` : `otel_enabled: bool = False`, `otel_endpoint: str | None`.
3. `main.py` : `configure_tracing(...)` dans `create_app`, `instrument_app(app)`,
   `instrument_engine(engine.sync_engine)` dans le `lifespan`.
4. Lance `APP_OTEL_ENABLED=true fastapi dev taskman/main.py`, fais une requête, observe les
   *spans* dans la console (un span HTTP + des spans SQL imbriqués).

**Critères d'acceptation**
- [ ] `otel_enabled=false` (défaut) → aucun span, aucune dépendance OTel chargée au *runtime*.
- [ ] `otel_enabled=true` sans endpoint → spans affichés en console.
- [ ] Une requête `GET /tasks/{id}` produit un span parent + des spans SQL enfants.

---

## Exercice 09.4 — Corréler trace ↔ logs 🟡

1. Ajoute le `trace_id` courant à chaque ligne de log (via `opentelemetry.trace.
   get_current_span().get_span_context().trace_id`, formaté en hex).
2. Vérifie : pendant une requête tracée, les logs du `JsonFormatter` contiennent `trace_id`
   **et** `request_id`.

**Critères d'acceptation**
- [ ] Un log émis hors requête n'a **ni** `trace_id` **ni** `request_id`.
- [ ] Un log émis pendant une requête tracée a les deux.

---

## Exercice 09.5 — Arrêt gracieux 🟡

1. Vérifie que le `lifespan` (`finally:`) ferme : le broker taskiq, le cache, le moteur DB.
2. Lance `fastapi run taskman/main.py`, envoie une requête **lente** (ajoute un
   `await asyncio.sleep(3)` temporaire), puis `Ctrl+C` : la requête en cours **termine**
   avant l'arrêt.
3. Retire le `sleep`.

**Critères d'acceptation**
- [ ] `Ctrl+C` ne coupe pas une requête en vol (arrêt gracieux d'Uvicorn).
- [ ] Aucune connexion DB ne « fuit » après l'arrêt (`SELECT count(*) FROM pg_stat_activity`).

---

## Exercice 09.6 — Dashboard & alertes (papier) 🟢

1. Rédige `observability/README.md` : les 5 métriques à surveiller, 4 règles d'alerte
   **actionnables** (condition + durée + quoi regarder).
2. **Bonus** : un `grafana-dashboard.json` avec les panneaux RED.

**Critères d'acceptation**
- [ ] Chaque alerte dit **quoi faire** quand elle se déclenche.
- [ ] Les seuils sont justifiés (pas « au pif »).

---

## Rendu

```bash
ruff check . && ruff format --check . && mypy taskman && pytest -m "not e2e"
git add -A && git commit -m "feat(module-09): métriques Prometheus (RED), traces OTel, /health vs /ready"
```

Puis [`../solutions/README.md`](../solutions/README.md) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

**Mini-projet associé** : [`statuspage`](../../projets/checkpoints/statuspage/BRIEF.md).
