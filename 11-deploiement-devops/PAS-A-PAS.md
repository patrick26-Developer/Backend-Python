# Module 11 — Explication pas à pas

> Ce module produit des fichiers d'**infrastructure**. Peu de Python (`Settings.root_path`).

---

## 1. `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder
```

- `# syntax=…` : active les fonctions modernes de BuildKit (`--mount`, etc.).
- `slim` : Debian minimal + Python. **Pas `alpine`** (musl casse certaines wheels), pas
  l'image complète (trop grosse).
- `AS builder` : nomme l'étage pour le référencer plus loin.

```dockerfile
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY taskman/__init__.py taskman/__init__.py
RUN pip install .
```

- **venv dans l'image** : on isole les deps de la lib Python système.
- **on copie SEULEMENT le manifeste** (`pyproject.toml`) + le strict minimum pour que
  `pip install .` fonctionne (hatchling a besoin du `__init__.py`).
- **layer caching** : Docker met en cache chaque instruction. Tant que `pyproject.toml` ne
  change pas, ce `RUN pip install` (lent) est **réutilisé**. Si on copiait tout le code
  avant, la moindre modif de `taskman/` réinstallerait toutes les dépendances.

```dockerfile
FROM python:3.13-slim AS runtime
ENV ... PYTHONPATH=/app ...
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app
COPY --from=builder /venv /venv
WORKDIR /app
COPY taskman/ ./taskman/
COPY alembic/ ./alembic/ alembic.ini ./
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
USER app
```

- **2ᵉ étage neuf** : il ne contient **que** ce qu'on y copie → pas de `gcc`, pas de cache
  pip, image finale bien plus légère.
- `COPY --from=builder /venv /venv` : on récupère uniquement l'environnement compilé.
- `PYTHONPATH=/app` : garantit que `import taskman` prend `/app/taskman/` (le code copié),
  pas une éventuelle version installée.
- **utilisateur non-root** (`USER app`) : une faille d'exécution de code ne donne pas
  `root` **dans le conteneur** (défense en profondeur).

```dockerfile
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; ... /health ..."

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["fastapi", "run", "taskman/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

- `HEALTHCHECK` : Docker/l'orchestrateur teste `/health` (liveness, Module 09). Un conteneur
  `unhealthy` est redémarré / sorti du LB.
- `start-period=10s` : on ne compte pas les échecs pendant le démarrage.
- **`ENTRYPOINT` + `CMD`** : l'entrypoint (le script) s'exécute **toujours** ; `CMD` est ses
  arguments (`exec "$@"`). `docker run taskman alembic downgrade -1` remplace le `CMD` mais
  passe quand même par l'entrypoint.
- `fastapi run` (≠ `fastapi dev`) : mode production, **pas** de `--reload`.

---

## 2. `.dockerignore`

```
.git
.venv
tests
site
0*-*/          # les dossiers de cours 01-… 12-…
*.md
!README.md
.env
!.env.example
```

Envoyé au démon Docker comme « contexte de build ». Sans `.dockerignore`, `docker build`
enverrait `.venv` (des centaines de Mo), `.git`, le site MkDocs… → build lent, image
potentiellement polluée, **secrets `.env` embarqués**.

---

## 3. `scripts/docker-entrypoint.sh`

```sh
#!/usr/bin/env sh
set -e
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    alembic upgrade head
fi
exec "$@"
```

- `set -e` : le script s'arrête à la première erreur.
- `RUN_MIGRATIONS` : **dev / compose** uniquement. En **prod**, les migrations sont une
  **étape de pipeline séparée** (une seule fois, avant le trafic) — sinon N conteneurs
  lancent `alembic upgrade` en même temps → *races*.
- `exec "$@"` : remplace le process du script par la commande (`fastapi run …`) → les
  signaux (`SIGTERM`) arrivent bien au serveur (arrêt gracieux).

---

## 4. `docker-compose.yml`

```yaml
services:
  api:
    build: .
    environment:
      APP_DATABASE_URL: postgresql+asyncpg://taskman:taskman@db:5432/taskman
      APP_REDIS_URL: redis://redis:6379/0
      RUN_MIGRATIONS: "true"
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
  db:
    image: postgres:17-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U taskman"]
```

- `db` / `redis` sont des **noms d'hôte** dans le réseau du compose (`@db:5432`).
- `condition: service_healthy` : l'API attend que `pg_isready` réponde — pas juste que le
  conteneur soit lancé.
- `volumes: [taskman_pgdata:/var/lib/postgresql/data]` : les données survivent à
  `docker compose down`.

---

## 5. `taskman/main.py` — `root_path`

```python
FastAPI(root_path=settings.root_path)   # "" par défaut, "/api" derrière un proxy
```

Si le proxy sert l'API sur `https://exemple.org/api/tasks`, FastAPI doit savoir que son
préfixe public est `/api` → sinon `openapi.json` déclare `/tasks` (faux) et le bouton
« Try it out » tape la mauvaise URL. `root_path` corrige tout ça sans changer les routes.

---

## 6. `.github/workflows/ci.yml`

```yaml
jobs:
  quality:
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    steps:
      - ruff check . && ruff format --check .
      - mypy taskman
      - alembic upgrade head && alembic check
      - pytest -m "not e2e" --cov=taskman --cov-report=term-missing

  security:
    steps:
      - pip install pip-audit && pip install -e "."   # deps de PROD seulement
      - pip-audit --strict --desc

  e2e:
    steps:
      - pytest -m e2e        # PostgreSQL réel (testcontainers)

  build:
    needs: [quality, security]
    steps:
      - uses: docker/metadata-action@v5
        with:
          tags: |
            type=sha           # taskman:sha-a1b2c3d
            type=semver,pattern={{version}}   # taskman:1.4.0 (sur tag v1.4.0)
      - uses: docker/build-push-action@v6
        with:
          push: ${{ github.event_name != 'pull_request' }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- **4 jobs** : `quality` + `security` **bloquent le merge** ; `e2e` informe ;
  `build` (dépend des deux premiers) produit l'artefact.
- **matrice** : on teste sur les 2 versions de Python supportées.
- **`build` ne pousse pas sur une PR** (`push: false`) — inutile de polluer le registre.
- **tags** : `sha-<court>` (toujours) + `X.Y.Z` (sur tag git `v*`). Une image **immuable** :
  `taskman:1.4.0` ne bougera jamais → rollback = redéployer `1.3.9`.
- **cache GitHub Actions** (`type=gha`) : les layers Docker sont réutilisés entre builds.

---

## 7. `CHANGELOG.md`

Format [Keep a Changelog](https://keepachangelog.com/) : une section `## [X.Y.Z] — date`
par version, avec `### Ajouté` / `### Modifié` / `### Corrigé`. `[Unreleased]` en haut pour
accumuler les changements en cours. Le `CHANGELOG` est **écrit à la main** (les messages de
commit ne suffisent pas — le lecteur veut savoir *ce qui change pour lui*, pas *comment*).

---

## Ce qui vient au Module 12

`taskman` est déployable. Le Module 12 revient sur l'**architecture** à grande échelle :
monolithe modulaire vs microservices, DDD léger, événements (*outbox*), versionnage d'API
(`/v1`), temps réel (SSE), idempotence — et refaire `taskman` de zéro comme examen final.
