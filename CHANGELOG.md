# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ·
Versionnage : [SemVer](https://semver.org/lang/fr/).

> `taskman` est le projet fil rouge du cursus : ses versions suivent les modules.

## [Unreleased]

## [0.11.0] — Module 11 — Déploiement & DevOps
### Ajouté
- `Dockerfile` multi-stage non-root + `HEALTHCHECK` ; `.dockerignore` ;
  `scripts/docker-entrypoint.sh`.
- `docker-compose.yml` complet (`api` + `db` + `redis`).
- `Settings.root_path` (API derrière un reverse proxy sous un sous-chemin).
- CI : jobs `build` (image taguée par SHA et version) et `e2e`.

## [0.10.0] — Module 10 — Sécurité approfondie
### Ajouté
- Rate limiting (`RateLimiter` mémoire/Redis) sur `/auth/*` → 429 + `Retry-After`.
- `SecurityHeadersMiddleware` (CSP sauf `/docs`, HSTS en prod), `BodySizeLimitMiddleware` (413).
- CORS configurable (`Settings.cors_origins`), jamais `*` + credentials.
- `SECURITY.md` (audit OWASP API Top 10) ; `pip-audit` en CI.

## [0.9.0] — Module 09 — Observabilité
### Ajouté
- Métriques Prometheus RED (`/metrics`), label `path` = template de route.
- Traçage OpenTelemetry (`configure_tracing`, auto-instrumentation), désactivé par défaut.
- `/health` (liveness) vs `/ready` (DB + cache → 503 si down).

## [0.8.0] — Module 08 — Async avancé & performance
### Ajouté
- Cache (`Cache` mémoire/Redis) + invalidation ; `GET /projects/{id}/stats`.
- Pagination *cursor* (`next_cursor`) ; export NDJSON streamé (`GET /tasks/export`).
- Notification à la complétion (`BackgroundTasks`) ; broker taskiq (`taskman/tasks.py`).
- `GZipMiddleware`.
### Modifié
- Repository : `list` → `list_page` (le nom masquait le type `list`).

## [0.7.0] — Module 07 — Tests
### Ajouté
- `POST /tasks/{id}/complete` + `completed_at` (développé en TDD).
- `tests/factories.py`, `tests/e2e/` (PostgreSQL via testcontainers), seuil de couverture 85 %.

## [0.6.0] — Module 06 — Authentification & autorisation
### Ajouté
- Comptes (`UserRow`), OAuth2 + JWT (access/refresh **avec rotation**), argon2.
- RBAC (`require_role`), isolation des données par `owner_id` (404 pour l'autrui).
- `/auth/*`, `/admin/*`.

## [0.5.0] — Module 05 — Erreurs, logs & middleware
### Ajouté
- Hiérarchie d'exceptions métier, handlers → format **Problem Details** (RFC 9457).
- `RequestContextMiddleware` (request-id, log d'accès), logs JSON corrélés.

## [0.4.0] — Module 04 — Bases de données
### Ajouté
- SQLAlchemy 2.0 async + Alembic ; `ProjectRow`/`TaskRow` ; repository SQL.
- Frontière transactionnelle dans le service (`commit`), `GET /projects`.

## [0.3.0] — Module 03 — Architecture d'un projet mature
### Modifié
- Découpage en couches `api / services / repositories` ; injection de dépendances ;
  `pydantic-settings` ; `create_app()` + `lifespan`.

## [0.2.0] — Module 02 — Modélisation & validation
### Ajouté
- Schémas `Create`/`Update`/`Read` séparés, `PATCH` correct, types riches, query model.

## [0.1.0] — Module 01 — Fondations HTTP & FastAPI
### Ajouté
- CRUD `tasks` en mémoire, typé et validé, auto-documenté.
