# Module 09 — Solutions : les choix de conception

> Snapshot `taskman` v0.9.0 dans [`taskman/`](taskman/). Explication ligne par ligne :
> [`../PAS-A-PAS.md`](../PAS-A-PAS.md). Métriques & alertes : [`taskman/observability/README.md`](taskman/observability/README.md).

```bash
pytest -m "not e2e"
fastapi dev taskman/main.py
curl -s localhost:8000/metrics | head
curl -s localhost:8000/ready | jq
APP_OTEL_ENABLED=true fastapi dev taskman/main.py   # spans en console
```

---

## Décisions

### 1. `/health` ≠ `/ready` — **la** distinction

`/health` (liveness) ne vérifie **rien** → il est 200 tant que le process tourne. Un
`/health` qui teste la DB provoque une **boucle de crash** au moindre incident DB. `/ready`
(readiness) teste DB + cache → **503** ⇒ le pod sort du load-balancer sans être tué, y
revient quand tout va bien.

### 2. Le label `path` est le **template**, jamais l'URL

`request.scope["route"].path` (`/tasks/{task_id}`), pas `request.url.path` (`/tasks/42`).
Une série Prometheus par identifiant = des millions de séries = Prometheus s'écroule. Un
test garde cette invariante (`test_metrics_path_label_is_route_template`).

### 3. Histogram pour la latence, pas Summary

`Histogram` (buckets) → Prometheus calcule les quantiles **côté serveur**, agrège plusieurs
instances. `Summary` calcule côté client et ne s'agrège pas. Buckets en secondes,
5 ms → 5 s.

### 4. OpenTelemetry : imports **paresseux**, désactivé par défaut

`configure_tracing` importe le SDK OTel **dans** la fonction, seulement si
`otel_enabled=true`. Défaut : rien n'est chargé, zéro surcoût. Auto-instrumentation
(FastAPI + SQLAlchemy) → spans sans toucher au code.

### 5. `/metrics` : `include_in_schema=False`, non authentifié, non public

Machine-to-machine (Prometheus). Pas dans `/docs`. **Pas** derrière l'auth (Prometheus ne
s'authentifie pas), **pas** exposé à l'extérieur (proxy / réseau interne).

### 6. `except Exception:` volontairement large dans `/ready`

N'importe quelle panne (timeout, connexion refusée, auth DB) doit donner `"fail"` +
503 — **pas** une 500. C'est un des rares cas où un `except` large est correct.

### 7. Arrêt gracieux = Uvicorn + `lifespan.finally`

Uvicorn attend les requêtes en vol sur `SIGTERM`. Le `finally:` du `lifespan` (Modules
04/08/09) ferme broker, cache, moteur DB → aucune connexion ne fuit au redéploiement.

### 8. Ordre des middlewares

De l'intérieur : GZip → Metrics → RequestContext. `RequestContext` externe (pose le
`request_id` avant tout) ; `Metrics` mesure hors compression.

---

## Grille d'auto-évaluation

- [ ] `/health` reste-t-il 200 quand la DB est coupée ?
- [ ] `/ready` renvoie-t-il 503 + `checks` détaillés quand une dépendance est down ?
- [ ] Le label `path` de tes métriques est-il borné (template, pas URL) ?
- [ ] `otel_enabled=false` → OTel n'est-il **jamais** importé au runtime ?
- [ ] `/metrics` est-il hors de `/docs` et non authentifié ?
- [ ] Le `lifespan.finally` ferme-t-il **toutes** les ressources ?

➡️ [Module 10 — Sécurité approfondie](../../10-securite-approfondie/THEORIE.md)
