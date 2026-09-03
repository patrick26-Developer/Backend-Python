# ROADMAP — Backend-Python / FastAPI

Ce document décrit le parcours complet : objectifs, contenu théorique, compétences visées,
exercices et **definition of done** (DoD) de chaque module. La DoD est ta grille
d'auto-évaluation : tant qu'une case n'est pas cochée *honnêtement*, le module n'est pas fini.

**Principe pédagogique** : chaque module suit la boucle
**Théorie courte → Exercice → Solution commentée → Intégration dans `taskman` → Commit.**

Légende difficulté : 🟢 accessible · 🟡 demande de la rigueur · 🔴 exigeant.

### État de rédaction de la formation

| Module | Théorie | Exercices | Solutions + PAS-A-PAS |
|---|:-:|:-:|:-:|
| 00 · Setup | ✅ | ✅ | — |
| 01 · Fondations HTTP & FastAPI | ✅ | ✅ | ✅ |
| 02 · Modélisation & validation | ✅ | ✅ | ✅ |
| 03 · Architecture d'un projet mature | ✅ | ✅ | ✅ |
| 04 · Bases de données (SQLAlchemy async + Alembic) | ✅ | ✅ | ✅ |
| 05 · Erreurs, logs & middleware | ✅ | ✅ | ✅ |
| 06 · Authentification & autorisation | ✅ | ✅ | ✅ |
| 07 · Tests (pyramide, factories, testcontainers, TDD) | ✅ | ✅ | ✅ |
| 08 · Async avancé & performance (cache, cursor, streaming, workers) | ✅ | ✅ | ✅ |
| 09 · Observabilité & prod-readiness (Prometheus, OTel, health/ready) | ✅ | ✅ | ✅ |
| 10 · Sécurité approfondie (OWASP API Top 10, rate limit, en-têtes, CORS) | ✅ | ✅ | ✅ |
| 11 · Déploiement & DevOps (Docker, compose, CI/CD, migrations en prod) | ✅ | ✅ | ✅ |
| 12 · Architecture & scalabilité (outbox, idempotence, versionnage, SSE) | ✅ | ✅ | ✅ |

> La formation se construit module par module. Chaque module livré : théorie, exercices,
> solutions complètes testées (`ruff` + `mypy --strict` + `pytest` au vert) et explication
> ligne par ligne.

---

## Module 00 — Setup & outillage professionnel 🟢

**Pourquoi.** Un backend de qualité commence par un environnement reproductible. Un projet
mal outillé accumule la dette dès le premier jour.

**Théorie.**
- Isolation des dépendances : `venv`, `pip`, `pip install -e`, `pyproject.toml` vs
  `requirements.txt`, verrouillage de versions. Alternative moderne : `uv`.
- Le triptyque qualité : **formatage** (ruff format), **lint** (ruff check),
  **typage statique** (mypy `--strict`).
- Hooks `pre-commit` : empêcher un commit non conforme.
- Structure d'un dépôt Python : *src layout* vs *flat layout*, où vivent les tests.
- Automatisation : `Makefile` / scripts de tâches.

**Compétences visées.** Créer un projet neuf, installable, lintable, typable, testable en
moins de 10 minutes, sans réfléchir.

**Exercices.** (1) Monter le squelette `taskman` from scratch. (2) Configurer ruff + mypy
et faire passer un fichier volontairement sale. (3) Écrire un `Makefile` (`make install`,
`make lint`, `make test`, `make run`).

**Livrable `taskman`.** Dossier `taskman/` avec `main.py` minimal, `pyproject.toml`
configuré, `make lint` et `make test` verts.

**DoD.**
- [ ] `pip install -e ".[dev]"` fonctionne dans un `.venv` neuf.
- [ ] `ruff check .` et `ruff format --check .` passent.
- [ ] `mypy taskman` passe en `--strict`.
- [ ] `pytest` s'exécute (même sans test réel).
- [ ] `.gitignore`, `.env.example`, `README` présents.

---

## Module 01 — Fondations HTTP & FastAPI 🟢

**Pourquoi.** Avant les patterns, il faut comprendre ce qu'est une requête, une réponse, un
code de statut, et comment FastAPI transforme des annotations Python en API documentée.

**Théorie.**
- HTTP : méthodes (GET/POST/PUT/PATCH/DELETE), codes de statut (2xx/4xx/5xx),
  en-têtes, idempotence, sémantique REST des ressources.
- ASGI vs WSGI : pourquoi FastAPI est *async-first*, rôle d'Uvicorn.
- FastAPI : `path`, `query`, `body` params ; inférence par annotation de type ;
  `Path()`, `Query()` et leurs validations ; modèles Pydantic v2 comme corps de requête.
- OpenAPI / Swagger UI / ReDoc générés automatiquement : `/docs`, `/openapi.json`.
- Pydantic v2 : `BaseModel`, types, contraintes (`Field`), `model_validator`, coercition.

**Compétences visées.** Écrire un CRUD complet, typé, validé et auto-documenté, sans base
de données.

**Exercices.** Voir [`01-fondations-http-et-fastapi/exercices/`](01-fondations-http-et-fastapi/exercices/).

**Livrable `taskman`.** CRUD `tasks` en mémoire : `POST /tasks`, `GET /tasks`,
`GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, avec filtres de query,
codes de statut corrects et 404 propre.

**DoD.**
- [ ] Les 5 opérations existent avec les bons *status codes* (201 à la création, 204 à la suppression…).
- [ ] Entrées invalides → 422 automatique et lisible.
- [ ] `/docs` décrit correctement chaque endpoint (exemples, schémas).
- [ ] Aucun `dict` non typé ne traverse une signature de fonction.
- [ ] `mypy --strict` et `ruff` passent.

---

## Module 02 — Modélisation & validation des données 🟡

**Pourquoi.** La plupart des bugs d'API sont des bugs de *contrat de données*. On sépare
strictement ce qui entre, ce qui est stocké, ce qui sort.

**Théorie.**
- Schémas dédiés : `TaskCreate`, `TaskUpdate`, `TaskRead` — jamais un seul modèle « à tout faire ».
- `response_model`, `response_model_exclude_unset`, filtrage des champs sensibles.
- Validation avancée : validateurs de champ et de modèle, types contraints, `Annotated`,
  `EmailStr`, `AwareDatetime`, énumérations.
- `PATCH` partiel : le problème du « null explicite vs absent », `exclude_unset`.
- Exemples et documentation : `model_config` / `json_schema_extra`.
- Introduction au versionnage des schémas.

**Compétences visées.** Concevoir des contrats d'API explicites, impossibles à mal utiliser.

**Exercices.** (1) Éclater le modèle unique en 3 schémas. (2) Implémenter un `PATCH`
correct. (3) Ajouter des règles métier de validation (date d'échéance future, titre non
vide après *strip*, priorité dans un enum).

**Livrable `taskman`.** `schemas/task.py` avec séparation nette ; réponses filtrées ;
`PATCH` sémantiquement correct.

**DoD.**
- [ ] Impossible de fixer un champ « serveur » (`id`, `created_at`) via le body.
- [ ] `PATCH {"description": null}` efface, `PATCH {}` ne touche à rien.
- [ ] Règles métier testées (cas passant + cas rejeté).
- [ ] Schémas documentés avec exemples dans `/docs`.

---

## Module 03 — Architecture d'un projet mature 🟡

**Pourquoi.** Un fichier `main.py` de 800 lignes ne scale pas — ni en équipe, ni en tête.

**Théorie.**
- `APIRouter` : découpage par domaine, préfixes, tags, `include_router`.
- Architecture en couches : **router** (HTTP) → **service** (métier) → **repository**
  (persistance). Pourquoi cette séparation, ce qui appartient à chaque couche.
- Injection de dépendances FastAPI : `Depends`, dépendances imbriquées, `yield` et cycle de
  vie, surcharge en test (`app.dependency_overrides`).
- Configuration : `pydantic-settings`, `.env`, `@lru_cache` sur `get_settings`,
  config par environnement (local/test/staging/prod).
- `lifespan` : initialisation/teardown des ressources.
- Arborescence cible d'un projet FastAPI.

**Compétences visées.** Organiser une base de code pour qu'un nouvel arrivant trouve
n'importe quoi en moins d'une minute.

**Exercices.** (1) Migrer le CRUD vers `api/ + services/ + repositories/`.
(2) Créer `core/config.py` typé et injecté. (3) Écrire un `InMemoryTaskRepository` derrière
une interface (`Protocol`), injecté par `Depends`.

**Livrable `taskman`.** Arborescence en couches, config injectée, repository abstrait
(encore en mémoire), routers séparés.

**DoD.**
- [ ] Aucune logique métier dans les fonctions de route.
- [ ] Aucune dépendance directe à un framework dans la couche service.
- [ ] La config n'est jamais lue via `os.environ` hors de `core/config.py`.
- [ ] Un test peut remplacer le repository par un faux via `dependency_overrides`.

---

## Module 04 — Bases de données : SQLAlchemy 2.0 async + Alembic 🔴

**Pourquoi.** La persistance est là où se jouent la cohérence, la performance et 90 % des
incidents de prod.

**Théorie.**
- SQLAlchemy 2.0 style : `DeclarativeBase`, `Mapped`, `mapped_column`, relations.
- Moteur async (`create_async_engine`, `asyncpg`), `async_sessionmaker`, session par requête
  via dépendance, `expire_on_commit`.
- Transactions : *unit of work*, `commit`/`rollback`, où placer la frontière transactionnelle
  (réponse : la couche service).
- *Repository pattern* concret sur SQLAlchemy ; mapping entité ORM ↔ schéma Pydantic.
- Migrations Alembic : autogénération, revue des migrations, `upgrade`/`downgrade`,
  migrations de données.
- Pièges : N+1, *lazy loading* en async, sessions partagées entre coroutines.

**Compétences visées.** Faire persister proprement une API async sans fuite de session ni
incohérence transactionnelle.

**Exercices.** (1) Modèle `Task` + `Project` avec relation. (2) Brancher le repository sur
la DB. (3) Générer et appliquer les migrations. (4) Écrire une requête filtrée + paginée
sans N+1.

**Livrable `taskman`.** `taskman` sur PostgreSQL (via `docker-compose`), `Project` et `Task`
liés, migrations versionnées.

**DoD.**
- [ ] `alembic upgrade head` monte une base vide au schéma courant.
- [ ] Une session = une requête HTTP ; rollback automatique en cas d'exception.
- [ ] Les tests tournent sur une base isolée (jetable).
- [ ] Aucune requête N+1 sur les *endpoints* de liste (vérifié via echo SQL).

---

## Module 05 — Erreurs, logs & middleware 🟡

**Pourquoi.** Une API sérieuse échoue de façon *prévisible* et *traçable*.

**Théorie.**
- Hiérarchie d'exceptions métier (`DomainError`, `NotFoundError`, `ConflictError`…) découplée
  de HTTP.
- `exception_handler` : traduire une exception métier en réponse HTTP normalisée
  (format type *Problem Details* / RFC 9457).
- `HTTPException` vs exceptions personnalisées : quand utiliser quoi.
- Middleware ASGI : `request-id`, mesure de latence, logs d'accès.
- Logging structuré (JSON), niveaux, corrélation par `request-id`, ne jamais logguer de
  secret.
- Gestion des erreurs de validation (`RequestValidationError`).

**Compétences visées.** Diagnostiquer un incident à partir des seuls logs.

**Exercices.** (1) Créer la hiérarchie d'exceptions + handlers. (2) Middleware `request-id`
propagé dans chaque log. (3) Uniformiser toutes les réponses d'erreur.

**Livrable `taskman`.** Format d'erreur unique documenté, logs JSON corrélés, middleware de
traçage.

**DoD.**
- [ ] Toutes les erreurs (404, 409, 422, 500) sortent avec le même schéma JSON.
- [ ] Chaque ligne de log porte le `request-id` de la requête.
- [ ] Une 500 ne fuit jamais de *stack trace* au client.
- [ ] Les exceptions métier ne connaissent pas `fastapi`.

---

## Module 06 — Authentification & autorisation 🔴

**Pourquoi.** L'auth mal faite = fuite de données. C'est le sujet où « ça marche » ne suffit pas.

**Théorie.**
- Authentification vs autorisation.
- Hachage de mots de passe : `argon2` / `bcrypt`, *salting*, jamais de MD5/SHA nu.
- OAuth2 *password flow* dans FastAPI, `OAuth2PasswordBearer`.
- JWT : structure, signature, `exp`, access token court + refresh token, rotation,
  révocation (liste noire / `jti`).
- Dépendances de sécurité : `get_current_user`, `get_current_active_user`.
- Autorisation : RBAC (rôles), *scopes* OAuth2, autorisation au niveau ressource
  (« je ne vois que MES tâches »).
- Pièges : *timing attacks*, *token* dans l'URL, secrets en dur, CORS trop permissif.

**Compétences visées.** Protéger une API avec un modèle d'accès explicite et testé.

**Exercices.** (1) `User` + inscription + login → JWT. (2) `get_current_user` + route
protégée. (3) RBAC : `admin` peut tout, `member` seulement ses ressources.
(4) Refresh token avec rotation.

**Livrable `taskman`.** Comptes, login/refresh, routes protégées, isolation des données par
utilisateur, rôles.

**DoD.**
- [ ] Mots de passe hachés (argon2/bcrypt), jamais réversibles ni logués.
- [ ] Un token expiré/altéré → 401 ; un accès à la ressource d'autrui → 403 ou 404.
- [ ] Le secret JWT vient de la config, différent par environnement.
- [ ] Tests : cas non authentifié, authentifié non autorisé, autorisé.

---

## Module 07 — Tests 🟡

**Pourquoi.** Sans tests, chaque refactor est un pari. La testabilité est une propriété
d'architecture.

**Théorie.**
- Pyramide des tests : unitaires (services, purs) vs intégration (API + DB) vs e2e.
- `pytest` : fixtures, *scopes*, paramétrage, marqueurs, `conftest.py`.
- `httpx.AsyncClient` + `ASGITransport` pour tester l'app sans serveur réseau.
- Base de test : transaction *rollback* par test, ou base jetable par session ; `testcontainers`.
- Données de test : *factories* (`factory_boy` / helpers), *fixtures* de builder.
- Surcharge de dépendances (`app.dependency_overrides`), *fakes* vs *mocks*.
- Couverture : la lire sans la fétichiser ; tester les branches d'erreur.
- TDD : le cycle rouge/vert/refactor sur un cas concret.

**Compétences visées.** Écrire une suite rapide, déterministe, qui donne confiance pour
refactorer.

**Exercices.** (1) Tester la couche service en isolation. (2) Tests d'intégration des
endpoints (cas passant + erreurs). (3) Un cas en TDD strict. (4) Fixtures de données
réutilisables.

**Livrable `taskman`.** `tests/` structuré (`unit/`, `integration/`), fixtures partagées,
couverture > 85 %, CI-ready.

**DoD.**
- [ ] `pytest` < quelques secondes, 100 % déterministe (aucun test « flaky »).
- [ ] Chaque endpoint a au moins un test passant et un test d'erreur.
- [ ] La couche service est testée sans HTTP ni DB réelle.
- [ ] La couverture des branches d'erreur est explicite.

---

## Module 08 — Async avancé & performance 🔴

**Pourquoi.** `async` mal utilisé est *plus lent* que du sync. La perf se conçoit, elle ne
se rajoute pas.

**Théorie.**
- Rappel *event loop* : ce qui bloque la boucle (CPU, I/O sync) et comment l'évi
  (`run_in_threadpool`, `asyncio.to_thread`).
- `BackgroundTasks` : pour quoi c'est fait, ses limites (même process, pas de reprise).
- File de tâches : `taskiq` / `ARQ` / Celery — quand passer à un worker externe.
- Cache : `Redis`, invalidation, *cache-aside*, clés, TTL, `Cache-Control`.
- Pagination : *offset* vs *keyset/cursor*, métadonnées de page.
- Optimisation DB : index, `selectinload`/`joinedload`, `EXPLAIN`, éviter le N+1.
- Mesure : *load testing* (`locust` / `k6`), lecture d'un profil.

**Compétences visées.** Identifier un goulot d'étranglement et choisir la bonne parade.

**Exercices.** (1) Déplacer l'envoi d'e-mail de notification en tâche de fond puis en worker.
(2) Ajouter un cache sur `GET /projects/{id}/stats`. (3) Pagination *cursor* sur `GET /tasks`.
(4) Corriger un N+1 introduit volontairement.

**Livrable `taskman`.** Notifications asynchrones, endpoint mis en cache, listes paginées en
*cursor*, requêtes optimisées.

**DoD.**
- [ ] Aucune opération bloquante dans une route `async` (vérifié).
- [ ] La tâche de fond survit à une erreur de la requête qui l'a déclenchée.
- [ ] Le cache a une stratégie d'invalidation écrite, pas seulement un TTL.
- [ ] Un test de charge simple montre le gain avant/après.

---

## Module 09 — Observabilité & prod-readiness 🟡

**Pourquoi.** « Ça marche chez moi » n'est pas un critère de prod. On doit *voir* le système.

**Théorie.**
- Les 3 piliers : logs, métriques, traces — ce que chacun résout.
- Métriques Prometheus : `RED` (Rate, Errors, Duration), `/metrics`, histogrammes de latence.
- Tracing distribué : OpenTelemetry, *spans*, propagation de contexte.
- Health checks : `/health` (liveness) vs `/ready` (readiness, vérifie DB/Redis).
- Config 12-factor : tout par variable d'environnement, artefact unique pour tous les envs.
- *Graceful shutdown*, gestion des signaux, *timeouts*.

**Compétences visées.** Rendre l'API exploitable par une équipe d'astreinte.

**Exercices.** (1) Exposer `/metrics` + latence par route. (2) `/health` et `/ready`
distincts. (3) Instrumenter une trace bout-en-bout sur une requête. (4) Vérifier le
*graceful shutdown*.

**Livrable `taskman`.** Endpoints d'exploitation, métriques RED, traces, config strictement
12-factor.

**DoD.**
- [ ] `/ready` échoue (503) si la DB est down ; `/health` reste 200.
- [ ] Latence p50/p95/p99 par endpoint visible dans les métriques.
- [ ] Une requête produit une trace corrélée aux logs (même id).
- [ ] Zéro valeur de config en dur dans le code.

---

## Module 10 — Sécurité approfondie 🔴

**Pourquoi.** La sécurité n'est pas une fonctionnalité, c'est une propriété transverse. On
la vérifie avec une méthode, pas au feeling.

**Théorie.**
- **OWASP API Security Top 10** (2023) : BOLA/IDOR, *broken authentication*,
  *broken object property level authorization*, *unrestricted resource consumption*,
  *broken function level authorization*, SSRF, mauvaise config, *inventory* d'API…
- *Rate limiting* & *throttling* (par IP, par utilisateur, par route).
- CORS : le comprendre vraiment (pré-vol, `credentials`, origines).
- En-têtes de sécurité : `HSTS`, `X-Content-Type-Options`, `Content-Security-Policy`…
- Validation stricte des entrées, limites de taille de payload, *mass assignment*.
- Gestion des secrets : *vault*, rotation, jamais dans git ; scan de dépendances (`pip-audit`).
- Journalisation de sécurité, *audit trail*.

**Compétences visées.** Auditer sa propre API avec la checklist OWASP et corriger les trous.

**Exercices.** (1) Trouver et corriger un IDOR dans `taskman`. (2) Ajouter un *rate limiter*.
(3) Durcir les en-têtes et le CORS. (4) Limiter la taille des payloads et la pagination.
(5) `pip-audit` en CI.

**Livrable `taskman`.** API durcie + `SECURITY.md` avec la checklist cochée.

**DoD.**
- [ ] Chaque accès à une ressource vérifie la propriété/le rôle (pas seulement l'auth).
- [ ] *Rate limiting* actif et testé.
- [ ] CORS restreint à des origines explicites ; pas de `*` avec credentials.
- [ ] `pip-audit` / scan de dépendances passe en CI.
- [ ] Checklist OWASP API Top 10 revue point par point.

---

## Module 11 — Déploiement & DevOps 🟡

**Pourquoi.** Le code n'a de valeur qu'une fois livré, de façon répétable et réversible.

**Théorie.**
- Docker : image multi-stage, *layer caching*, utilisateur non-root, `.dockerignore`,
  image *slim/distroless*, `HEALTHCHECK`.
- `docker-compose` pour le dev (API + Postgres + Redis).
- Serveur de prod : Uvicorn workers, ou Gunicorn + `UvicornWorker`, dimensionnement,
  reverse proxy.
- Migrations en prod : *quand* les jouer, compatibilité ascendante/descendante,
  déploiements sans coupure.
- CI/CD GitHub Actions : lint + type + test + build + scan, matrice de versions, cache,
  publication d'image.
- *Release* : versionnage sémantique, *changelog*, artefact immuable.

**Compétences visées.** Livrer une nouvelle version en une commande, et la *rollback* en une
commande.

**Exercices.** (1) `Dockerfile` multi-stage < 200 Mo, non-root. (2) `docker-compose` de dev
complet. (3) Workflow CI qui bloque le *merge* si lint/type/test échoue. (4) Job qui
construit et pousse l'image sur *tag*.

**Livrable `taskman`.** Image de prod, `docker-compose.yml`, `.github/workflows/ci.yml`,
procédure de déploiement + rollback documentée.

**DoD.**
- [ ] `docker compose up` démarre toute la stack de dev.
- [ ] L'image de prod tourne en non-root et passe son `HEALTHCHECK`.
- [ ] La CI échoue si `ruff`, `mypy` ou `pytest` échoue.
- [ ] Les migrations sont jouées de façon contrôlée, pas au démarrage de l'app en aveugle.

---

## Module 12 — Architecture & scalabilité 🔴

**Pourquoi.** Savoir *quand ne pas* découper est aussi important que savoir découper.

**Théorie.**
- Monolithe modulaire vs microservices : coûts réels, *quand* migrer, *modular monolith*
  comme défaut sain.
- DDD léger : *bounded contexts*, langage ubiquitaire, entités/agrégats/*value objects*,
  où placer les règles.
- *Event-driven* : événements de domaine, *outbox pattern*, idempotence des consommateurs.
- Versionnage d'API : URI vs header, dépréciation, cycle de vie.
- Temps réel : WebSockets vs SSE — cas d'usage, *scaling* (Redis pub/sub).
- Idempotence des écritures : `Idempotency-Key`, *at-least-once*.
- Multi-instance : *statelessness*, sessions, *sticky* vs partagé, *background jobs* distribués.

**Compétences visées.** Défendre un choix d'architecture avec des arguments de coût et de
risque, pas de mode.

**Exercices.** (1) Réorganiser `taskman` en modules par *bounded context*. (2) Émettre un
événement `TaskCompleted` via *outbox* consommé par un worker. (3) Versionner l'API (`/v1`,
`/v2`) avec une route qui change de contrat. (4) Notifications temps réel via SSE.
(5) Rendre `POST /tasks` idempotent.

**Livrable `taskman`.** Découpage modulaire documenté (ADR), événement d'exemple, API
versionnée, flux SSE, écriture idempotente.

**DoD.**
- [ ] Un `docs/adr/` contient au moins 3 décisions d'architecture datées et motivées.
- [ ] Les modules ne s'appellent qu'via des interfaces publiques explicites.
- [ ] `POST` avec la même `Idempotency-Key` ne crée qu'une ressource.
- [ ] L'API `/v1` reste stable quand `/v2` évolue.

---

## Après la roadmap

- Refais `taskman` **from scratch** en 2 jours, sans regarder : c'est le vrai test.
- Attaque un second projet d'un autre domaine (e-commerce, SaaS multi-tenant) pour
  généraliser les patterns.
- Contribue à un projet FastAPI open-source.
- Lis le code source de FastAPI et de Starlette.

## Ressources de référence

- FastAPI — doc officielle : <https://fastapi.tiangolo.com>
- Starlette (le socle ASGI) : <https://www.starlette.io>
- Pydantic v2 : <https://docs.pydantic.dev>
- SQLAlchemy 2.0 : <https://docs.sqlalchemy.org>
- OWASP API Security Top 10 : <https://owasp.org/API-Security/>
- The Twelve-Factor App : <https://12factor.net>
- RFC 9457 (Problem Details) : <https://www.rfc-editor.org/rfc/rfc9457>
