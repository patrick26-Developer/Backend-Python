# Module 11 — Déploiement & DevOps

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

**Livrer une version en une commande, la *rollback* en une commande.** Le code n'a de valeur
qu'une fois livré, de façon répétable et réversible.

## Pages de doc FastAPI couvertes

Deployment : About FastAPI versions · About HTTPS · Run a Server Manually · Deployments
Concepts · Deploy on Cloud Providers · Server Workers - Uvicorn with Workers · FastAPI in
Containers - Docker · Behind a Proxy · Generating SDKs (annexe) · Reference : `FastAPI CLI`.

## Plan

1. Docker : image multi-stage, *layer caching*, non-root, `.dockerignore`, `HEALTHCHECK`.
2. `docker-compose` de dev (API + Postgres + Redis).
3. Serveur de prod : Uvicorn workers / Gunicorn + `UvicornWorker`, dimensionnement, proxy.
4. `--root-path` derrière un reverse proxy.
5. Migrations en prod : quand, compatibilité ascendante/descendante, zéro coupure.
6. CI/CD GitHub Actions : lint + type + test + build + scan, matrice, cache, publication d'image.
7. Versionnage sémantique, *changelog*, artefact immuable.

## Exercices (aperçu)

- `Dockerfile` multi-stage < 200 Mo, non-root, `HEALTHCHECK` vert.
- `docker-compose.yml` : `docker compose up` démarre toute la stack.
- Workflow CI qui bloque le *merge* si `ruff`/`mypy`/`pytest` échoue.
- Job qui build + push l'image sur *tag* Git.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
