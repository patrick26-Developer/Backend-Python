# Module 09 — Observabilité & prod-readiness

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Rendre l'API **exploitable par une équipe d'astreinte** : on doit *voir* le système.

## Pages de doc FastAPI couvertes

Metadata and Docs URLs · Static Files · Templates (annexe) · Conditional OpenAPI ·
Configure Swagger UI (annexe) · Custom Docs UI Static Assets (annexe) · Reference :
`OpenAPI`, `OpenAPI docs`, `Templating - Jinja2Templates`, `Static Files - StaticFiles`.

## Plan

1. Les 3 piliers : logs, métriques, traces — ce que chacun résout.
2. Métriques Prometheus : `RED` (Rate, Errors, Duration), `/metrics`, histogrammes.
3. Tracing OpenTelemetry : *spans*, propagation de contexte, corrélation aux logs.
4. Health checks : `/health` (liveness) vs `/ready` (readiness : DB, Redis).
5. Config 12-factor : tout par variable d'env, artefact unique.
6. *Graceful shutdown*, signaux, *timeouts*.
7. OpenAPI conditionnel (docs désactivées en prod si besoin).

## Exercices (aperçu)

- `/metrics` + latence p50/p95/p99 par route.
- `/health` et `/ready` distincts ; `/ready` → 503 si DB down.
- Trace bout-en-bout d'une requête, corrélée au `request-id`.
- **Mini-projet `statuspage`** (voir [`../projets/`](../projets/README.md)).

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
