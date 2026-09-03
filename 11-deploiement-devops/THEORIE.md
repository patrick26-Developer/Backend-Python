# Module 11 — Déploiement & DevOps

> **Objectif** : **livrer une version en une commande, la *rollback* en une commande.**
> Docker multi-stage, `docker-compose`, workers Uvicorn/Gunicorn, migrations en prod,
> reverse proxy, CI/CD.
> Le code n'a de valeur qu'une fois **livré**, de façon répétable et réversible.
>
> **Durée estimée** : 10 à 14 h. **Pré-requis** : Modules 04, 09, 10.

---

## 1. Docker : une image d'application

Une **image** = le code + ses dépendances + un runtime, figés. Un **conteneur** = une
instance qui tourne. Objectif : la **même** image de la machine du dev jusqu'à la prod
(12-factor V. « Build, release, run »).

### Multi-stage build

```dockerfile
# --- étage 1 : build (a les outils de compilation) ---
FROM python:3.13-slim AS builder
WORKDIR /app
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
COPY pyproject.toml ./
RUN pip install --no-cache-dir .          # installe les deps dans /venv

# --- étage 2 : runtime (minimal) ---
FROM python:3.13-slim
RUN useradd -m -u 1000 app                 # PAS root
COPY --from=builder /venv /venv
COPY taskman/ /app/taskman/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
WORKDIR /app
ENV PATH="/venv/bin:$PATH"
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["fastapi", "run", "taskman/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

Pourquoi **multi-stage** : l'étage `builder` a `gcc`, les headers, le cache pip… ; l'image
finale ne garde que le `/venv` compilé + le code → **plus petite** (moins de surface
d'attaque) et **plus rapide** à télécharger.

### Les bonnes pratiques

| Règle | Pourquoi |
|---|---|
| **`slim`** (pas `alpine`) | `alpine` utilise musl → bugs subtils avec certaines wheels ; `distroless` en dernière étape pour aller plus loin |
| **utilisateur non-root** (`USER app`) | une faille RCE ne donne pas root dans le conteneur |
| **`.dockerignore`** | ne pas copier `.venv`, `.git`, `tests/`, `site/` dans l'image |
| **layer caching** : `COPY pyproject.toml` **avant** `COPY taskman/` | changer le code ne réinstalle pas les deps |
| **`HEALTHCHECK`** | Docker/l'orchestrateur sait si le conteneur est sain |
| **pas de secret dans l'image** | ils viennent de l'environnement au *run*, jamais du `build` |
| **tag précis** (`python:3.13.5-slim`) + image applicative taguée par version/SHA | reproductibilité, rollback |

---

## 2. `docker-compose` pour le dev

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      APP_DATABASE_URL: postgresql+asyncpg://taskman:taskman@db:5432/taskman
      APP_REDIS_URL: redis://redis:6379/0
      RUN_MIGRATIONS: "true"
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
  db: { image: postgres:17-alpine, ... , healthcheck: {...} }
  redis: { image: redis:7-alpine, ... }
```

```bash
docker compose up --build    # toute la stack, en une commande
```

`depends_on: {condition: service_healthy}` → l'API ne démarre pas avant que Postgres réponde
à `pg_isready`.

---

## 3. Serveur de production : workers

Uvicorn seul = **1 process**, 1 cœur. Pour utiliser toute la machine :

```bash
fastapi run taskman/main.py --workers 4
# ou : gunicorn taskman.main:app -k uvicorn.workers.UvicornWorker -w 4
```

- **combien de workers ?** règle de départ : `2 × CPU + 1`. À ajuster selon la charge
  (CPU-bound → moins ; I/O-bound async → un worker sature déjà bien un cœur).
- **chaque worker** a son propre *event loop*, son pool de connexions DB
  → `workers × pool_size ≤ max_connections` de PostgreSQL (sinon « too many connections »).
- **`--workers` vs répliques** : plusieurs conteneurs à 1 worker (K8s) *ou* 1 conteneur à N
  workers (VM). Le premier scale mieux, le second est plus simple.
- **redémarrage** : `--reload` **jamais** en prod (surveille les fichiers, fuit de la
  mémoire).

---

## 4. Derrière un reverse proxy

En prod, l'API n'est **pas** exposée directement. Devant : Nginx / Traefik / un load
balancer cloud qui fait :

- **terminaison TLS** (HTTPS) → l'API parle HTTP en interne ;
- **répartition** entre les répliques ;
- **timeouts**, limites de taille, en-têtes ;
- route `/metrics`, `/ready` **bloquées** de l'extérieur.

### Les en-têtes `X-Forwarded-*`

Le proxy pose `X-Forwarded-For` (IP client), `X-Forwarded-Proto` (https), `X-Forwarded-Host`.
Uvicorn doit **faire confiance** à ces en-têtes — mais seulement s'ils viennent du proxy :

```bash
fastapi run ... --forwarded-allow-ips "10.0.0.0/8"   # l'IP/réseau du proxy
```

Sans ça, `request.client.host` = l'IP du proxy (rate limiting cassé — Module 10), et
`request.url.scheme` = `http` (liens `Location` erronés).

### `root_path` (API sous un sous-chemin)

Si le proxy sert l'API sur `https://exemple.org/api/…`, FastAPI doit le savoir pour générer
les bons liens et le bon `/api/docs` :

```python
FastAPI(root_path=settings.root_path)   # "/api"
```

---

## 5. Migrations en production

**Le** sujet délicat. Une migration change le schéma pendant que du code tourne.

### Quand jouer les migrations ?

| Approche | Pour | Contre |
|---|---|---|
| **au démarrage du conteneur** (entrypoint) | simple | N conteneurs = N `alembic upgrade` concurrents ; un échec bloque le démarrage |
| **job/étape séparé** avant le déploiement | contrôlé, une seule fois, rollback possible | un pas de plus dans le pipeline |

**Recommandé en prod** : une **étape de pipeline** `alembic upgrade head` **avant** de
router le trafic vers la nouvelle version. `taskman` fournit un entrypoint avec
`RUN_MIGRATIONS=true` pour le dev, mais documente l'étape séparée pour la prod.

### Migrations **compatibles** (déploiement sans coupure)

Pendant un déploiement progressif, **l'ancienne et la nouvelle version du code coexistent**.
La migration doit être compatible avec **les deux**.

| Changement | Sûr en une fois ? | Sinon |
|---|---|---|
| ajouter une colonne **nullable** / avec défaut | ✅ | — |
| ajouter un index | ✅ (`CREATE INDEX CONCURRENTLY` sur Postgres) | — |
| **supprimer** une colonne | ❌ | 2 déploiements : (1) le code arrête de l'utiliser, (2) la migration la supprime |
| **renommer** une colonne | ❌ | ajouter la nouvelle + copier + basculer le code + supprimer l'ancienne (4 étapes) |
| ajouter une colonne **NOT NULL** sans défaut | ❌ | ajouter nullable → *backfill* → passer NOT NULL |
| changer un type | ❌ souvent | nouvelle colonne + migration de données |

### `alembic downgrade`

Prévois toujours le `downgrade`. Mais : un `downgrade` qui **perd des données** (colonne
supprimée) n'est pas un vrai rollback → dans ces cas, le rollback = redéployer l'**image**
précédente, pas défaire la migration.

---

## 6. CI/CD

```
push / PR
  ├─ lint (ruff)            ─┐
  ├─ types (mypy)            │  bloquent le merge
  ├─ tests + couverture      │
  ├─ pip-audit (sécurité)   ─┘
  │
  └─ (sur tag v*)  build image ─▶ push registry ─▶ deploy staging ─▶ (manuel) deploy prod
```

- **CI** (à chaque PR) : qualité + tests. Rapide (< 10 min), sinon on la contourne.
- **CD** (sur `main` ou sur *tag*) : build de l'image (taguée par SHA **et** version),
  push, déploiement.
- **matrice** : tester sur 3.12 **et** 3.13 (les deux versions supportées).
- **cache** : dépendances pip, layers Docker → CI rapide.
- **artefact immuable** : l'image `taskman:1.4.2` ne change **jamais**. Rollback = redéployer
  `taskman:1.4.1`.

### Versionnage sémantique

`MAJEUR.MINEUR.CORRECTIF` :
- **CORRECTIF** (`1.4.1 → 1.4.2`) : bug fix, rétrocompatible ;
- **MINEUR** (`1.4 → 1.5`) : nouvelle fonctionnalité, rétrocompatible ;
- **MAJEUR** (`1.x → 2.0`) : changement cassant du contrat public.

Un `CHANGELOG.md` (format *Keep a Changelog*) résume chaque version.

---

## 7. Stratégies de déploiement

| Stratégie | Principe | Rollback |
|---|---|---|
| **Recreate** | on arrête tout, on redémarre | coupure ; simple |
| **Rolling** | on remplace les répliques une par une | pas de coupure ; les 2 versions coexistent (→ migrations compatibles) |
| **Blue-Green** | 2 environnements complets, on bascule le trafic | instantané ; coûteux (× 2) |
| **Canary** | 5 % du trafic sur la nouvelle version, puis 25 %, 100 % | rapide ; demande des métriques fines |

`taskman` (simple) : **rolling**. Prérequis : health checks (Module 09) + migrations
compatibles (§5).

---

## 8. Pièges fréquents

1. **`--reload` en prod** → fuite mémoire, CPU gaspillé.
2. **Image qui tourne en root** → une RCE = root dans le conteneur.
3. **Secret dans le `Dockerfile`** (`ENV JWT_SECRET=...`) → il est dans l'historique de
   l'image, extractible.
4. **`alembic upgrade` au démarrage de N conteneurs** → *races*, *deadlocks*.
5. **Migration non compatible** pendant un rolling deploy → l'ancienne version crashe.
6. **`X-Forwarded-For` sans `--forwarded-allow-ips`** → IP client = IP du proxy.
7. **`COPY . .` avant `pip install`** → chaque changement de code réinstalle tout.
8. **Pas de `HEALTHCHECK`** → l'orchestrateur route du trafic vers un conteneur mort.
9. **Tag `latest`** partout → impossible de savoir/rollback ce qui tourne.
10. **CI de 40 min** → l'équipe la contourne, la qualité chute.

---

## 9. Ce que `taskman` gagne

- `Dockerfile` multi-stage, non-root, `HEALTHCHECK`, < 200 Mo ;
- `.dockerignore` ;
- `docker-compose.yml` complet (`api` + `db` + `redis`), `docker compose up` = toute la stack ;
- `scripts/docker-entrypoint.sh` (migrations conditionnelles + serveur) ;
- `Settings.root_path`, `Settings.workers` ; `fastapi run --workers` ;
- `.github/workflows/` : CI (lint/type/test/audit/migrations) + job `build` (image taguée
  par SHA et version) + job `e2e` ;
- `CHANGELOG.md`, `docs/deploiement.md` (procédure + rollback).

---

## 10. À savoir refaire sans aide

- Écrire un `Dockerfile` multi-stage non-root avec *layer caching* et `HEALTHCHECK`.
- Monter une stack locale complète avec `docker-compose`.
- Dimensionner les workers Uvicorn/Gunicorn en fonction des connexions DB.
- Configurer une app derrière un reverse proxy (`--forwarded-allow-ips`, `root_path`).
- Planifier des migrations **compatibles** pour un déploiement sans coupure.
- Bâtir un pipeline CI/CD : qualité bloquante + build d'artefact immuable + déploiement.
- Faire un rollback (redéployer l'image précédente).

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
