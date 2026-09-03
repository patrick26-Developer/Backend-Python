# Module 11 — Exercices

**Filet :** `git commit -m "checkpoint: avant module 11"`.
Ce module produit surtout des fichiers d'**infrastructure** (Dockerfile, compose, CI).

---

## Exercice 11.1 — `Dockerfile` multi-stage 🔴

1. Écris un `Dockerfile` :
   - **étage `builder`** : `python:3.13-slim`, crée `/venv`, installe les dépendances
     (`pip install .`) — copie **d'abord** `pyproject.toml` (layer caching) ;
   - **étage `runtime`** : `python:3.13-slim`, crée un utilisateur `app` (uid 1000),
     `COPY --from=builder /venv /venv`, copie `taskman/`, `alembic/`, `alembic.ini`,
     `USER app`, `EXPOSE 8000`, `HEALTHCHECK` sur `/health`,
     `CMD ["fastapi", "run", "taskman/main.py", "--host", "0.0.0.0"]`.
2. `.dockerignore` : exclut `.git`, `.venv`, `tests/`, `site/`, les dossiers de cours,
   `*.md` (sauf `README.md`), `.env*` (sauf `.env.example`).
3. `scripts/docker-entrypoint.sh` : si `RUN_MIGRATIONS=true`, `alembic upgrade head`, puis
   `exec "$@"`.

**Critères d'acceptation**
- [ ] `docker build -t taskman:local .` réussit.
- [ ] `docker run --rm taskman:local id` affiche `uid=1000(app)` (**pas** root).
- [ ] Image < 250 Mo (`docker images taskman`).
- [ ] `docker inspect` montre un `Healthcheck`.
- [ ] Changer une ligne de `taskman/` ne réinstalle **pas** les dépendances (cache).

---

## Exercice 11.2 — `docker-compose` complet 🟡

1. `docker-compose.yml` : services `api` (build `.`), `db` (postgres:17-alpine, healthcheck
   `pg_isready`), `redis` (redis:7-alpine, healthcheck `redis-cli ping`).
2. `api` : `depends_on` avec `condition: service_healthy` ; `APP_DATABASE_URL` et
   `APP_REDIS_URL` pointent vers `db` / `redis` ; `RUN_MIGRATIONS: "true"`.
3. Volume nommé pour les données PostgreSQL.

**Critères d'acceptation**
- [ ] `docker compose up --build` démarre toute la stack ; `/docs` répond.
- [ ] L'API attend que Postgres soit `healthy` avant de démarrer.
- [ ] Les migrations sont jouées au démarrage (`RUN_MIGRATIONS`).
- [ ] `docker compose down && up` conserve les données (volume).

---

## Exercice 11.3 — Workers & reverse proxy 🟡

1. `Settings.root_path: str = ""` ; passe-le à `FastAPI(root_path=settings.root_path)`.
2. Documente dans `docs/deploiement.md` :
   - le calcul du nombre de workers (`2 × CPU`, contrainte `workers × pool_size ≤
     max_connections`) ;
   - `fastapi run --workers N` ;
   - `--forwarded-allow-ips "<réseau du proxy>"` (pour que `X-Forwarded-For` soit fiable —
     Module 10) ;
   - `--reload` **interdit** en prod.
3. **Bonus** : un `nginx.conf` d'exemple (TLS, `proxy_pass`, `/metrics` bloqué de
   l'extérieur, `X-Forwarded-*`).

**Critères d'acceptation**
- [ ] Avec `APP_ROOT_PATH=/api`, `openapi.json` et les liens tiennent compte du préfixe.
- [ ] La doc explique le dimensionnement des workers, chiffres à l'appui.

---

## Exercice 11.4 — Migrations en production (théorie appliquée) 🔴

1. Rédige, dans `docs/deploiement.md`, la **procédure de release** : tag → CI → build →
   **migration (étape dédiée)** → déploiement rolling.
2. Pour 3 changements de schéma (**ajout de colonne nullable**, **suppression de colonne**,
   **renommage**), écris la (les) migration(s) **compatible(s)** avec un déploiement sans
   coupure, en indiquant le nombre de déploiements nécessaires.
3. Explique pourquoi `alembic downgrade` **n'est pas** toujours un rollback valide.

**Critères d'acceptation**
- [ ] La procédure ne joue **jamais** les migrations au démarrage de N conteneurs.
- [ ] Les 3 scénarios ont une stratégie compatible documentée.

---

## Exercice 11.5 — Pipeline CI/CD 🔴

1. `.github/workflows/ci.yml` :
   - job `quality` : `ruff`, `mypy`, `pytest -m "not e2e"` + couverture, `alembic check`
     (matrice 3.12 / 3.13) ;
   - job `security` : `pip-audit --strict` sur les deps de prod ;
   - job `e2e` : `pytest -m e2e` (PostgreSQL via testcontainers) ;
   - job `build` (dépend de `quality` + `security`) : build de l'image, tags
     `type=sha` **et** `type=semver`, push sur GHCR **hors PR**, cache `type=gha`.
2. Le *merge* est bloqué si `quality` ou `security` échoue (règles de protection de branche).

**Critères d'acceptation**
- [ ] Une PR déclenche `quality`, `security`, `e2e` mais **ne pousse pas** d'image.
- [ ] Un push sur `main` / un tag `v*` build **et** pousse l'image, taguée par SHA et version.
- [ ] La CI complète (hors e2e) tourne en < 10 min.

---

## Exercice 11.6 — `CHANGELOG` & release 🟢

1. `CHANGELOG.md` au format *Keep a Changelog* : une section par version (= par module),
   `Ajouté` / `Modifié` / `Corrigé`.
2. Cible `make release VERSION=x.y.z` (ou `.\tasks.ps1`) : bump `__version__`, met à jour le
   `CHANGELOG`, crée le tag git.

**Critères d'acceptation**
- [ ] Le `CHANGELOG` couvre les versions 0.1.0 → 0.11.0.
- [ ] `__version__` et le tag git concordent.

---

## Rendu

```bash
docker build -t taskman:local . && docker run --rm -p 8000:8000 --env-file .env taskman:local
docker compose up --build
ruff check . && mypy taskman && pytest -m "not e2e"
git add -A && git commit -m "feat(module-11): Docker multi-stage, docker-compose, CI/CD, migrations en prod"
```

Puis [`../solutions/README.md`](../solutions/) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).
