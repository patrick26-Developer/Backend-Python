# Backend-Python — Maîtriser FastAPI de zéro à la production

> **FR** — Un cursus complet, pratique et progressif pour concevoir, développer, tester et
> exploiter des API FastAPI de qualité professionnelle : robustes, sécurisées, scalables,
> modulaires et maintenables.
>
> **EN** — A complete, hands-on, progressive curriculum to design, build, test and operate
> production-grade FastAPI APIs: robust, secure, scalable, modular and maintainable.

<p align="center">
  <em>13 modules · théorie condensée · exercices + solutions · un projet fil rouge qui grandit à chaque module</em>
</p>

---

## Pour qui ? / Who is this for?

Tu connais **Python** (fonctions, classes, typage de base, `venv`) et tu veux passer du
statut de « développeur qui bricole des scripts » à celui d'**ingénieur backend** capable
de livrer une API que l'on peut faire tourner en production sans rougir.

Prérequis / Prerequisites :

| Attendu | Niveau |
|---|---|
| Python (syntaxe, classes, `list`/`dict`, décorateurs simples) | Confirmé |
| Ligne de commande, `git` | À l'aise |
| HTTP, REST, JSON, SQL de base | Notions — on consolide au fil des modules |
| Flask / Django / ORM / Docker | Utile mais **non requis** |

---

## Le projet fil rouge : `taskman`

Un **gestionnaire de tâches et de projets** (à la Todoist / Linear, en plus modeste).
On le construit brique par brique. Chaque module ajoute une capacité et une exigence de
qualité. À la fin, `taskman` est une API :

- structurée en couches (API / services / persistance) et découpée en modules ;
- validée de bout en bout avec Pydantic v2 ;
- adossée à PostgreSQL via SQLAlchemy 2.0 async + migrations Alembic ;
- authentifiée (OAuth2 + JWT) et autorisée (RBAC) ;
- testée (unitaires + intégration, couverture mesurée) ;
- observable (logs structurés, métriques, traces, health checks) ;
- déployée via Docker + CI GitHub Actions.

---

## Comment utiliser ce dépôt / How to use this repo

1. **Installe l'environnement** — suis [`00-setup/README.md`](00-setup/README.md).
2. **Travaille les modules dans l'ordre.** Chaque dossier `NN-...` contient :
   - `THEORIE.md` — la théorie *juste nécessaire*, avec les pourquoi et les pièges ;
   - `exercices/` — des énoncés progressifs (`README.md` + fichiers de départ) ;
   - `solutions/` — une solution commentée, testée, qui passe `ruff` + `mypy --strict` ;
   - `PAS-A-PAS.md` — l'explication **ligne par ligne** de la solution.
3. **Fais l'exercice AVANT de lire la solution.** La solution n'est pas un corrigé unique :
   c'est *une* bonne réponse parmi d'autres. Compare, ne recopie pas.
4. **Fais évoluer `taskman/`** à chaque module en repartant de l'état précédent.
5. **Commit à chaque étape.** L'historique git *est* ton cahier de progression.

> Règle d'or : **tu écris le code toi-même**. Lire du FastAPI ne l'apprend pas ; le taper,
> le casser, le typer et le tester, oui.

---

## Roadmap — vue d'ensemble

| # | Module | Tu sauras… | Livrable `taskman` |
|---|---|---|---|
| 00 | **Setup & outillage** | Monter un projet Python pro : `venv`, dépendances, `ruff`, `mypy`, pré-commit, `Makefile` | Squelette de projet qui lint/type/test |
| 01 | **Fondations HTTP & FastAPI** | HTTP/REST, ASGI, path/query/body params, docs OpenAPI auto, Pydantic v2 de base | CRUD `tasks` en mémoire, bien typé |
| 02 | **Modélisation & validation** | Schémas *request*/*response* séparés, `response_model`, validation avancée, versionnage des schémas | Schémas propres, entrées/sorties distinctes |
| 03 | **Architecture d'un projet mature** | `APIRouter`, `pydantic-settings`, architecture en couches, injection de dépendances | Découpage `api/services/repositories`, config par env |
| 04 | **Bases de données** | SQLAlchemy 2.0 async, sessions, *repository pattern*, transactions, migrations Alembic | `taskman` sur PostgreSQL + migrations |
| 05 | **Erreurs, logs & middleware** | Exceptions métier, *exception handlers*, réponses d'erreur cohérentes, logs structurés, request-id | Format d'erreur unifié, logs JSON corrélés |
| 06 | **Authentification & autorisation** | OAuth2 password flow, JWT access/refresh, hachage, RBAC, *scopes*, dépendances de sécurité | Login, utilisateurs, rôles, routes protégées |
| 07 | **Tests** | `pytest`, `httpx.AsyncClient`, fixtures, base de test isolée, *factories*, TDD, couverture | Suite de tests verte, couverture > 85 % |
| 08 | **Async avancé & performance** | `async`/`await` correct, *background tasks*, workers (taskiq/ARQ), cache Redis, pagination, N+1 | Tâches asynchrones + cache + pagination |
| 09 | **Observabilité & prod-readiness** | Logging, métriques Prometheus, tracing OpenTelemetry, `/health` & `/ready`, config 12-factor | Endpoints d'exploitation + métriques |
| 10 | **Sécurité approfondie** | OWASP API Security Top 10, *rate limiting*, CORS, en-têtes de sécurité, gestion des secrets | Durcissement complet + checklist sécurité |
| 11 | **Déploiement & DevOps** | Docker multi-stage, `docker-compose`, Uvicorn/Gunicorn, migrations en prod, CI GitHub Actions | Image de prod + pipeline CI |
| 12 | **Architecture & scalabilité** | Monolithe modulaire vs microservices, DDD léger, *event-driven*, versionnage d'API, WebSockets/SSE, idempotence | Choix d'archi documentés, API versionnée |

Détail complet, objectifs pédagogiques et « definition of done » de chaque module :
**[`ROADMAP.md`](ROADMAP.md)**.

Ce cursus **couvre l'intégralité de la documentation officielle FastAPI** (Tutorial,
Advanced User Guide, How-To, Reference, Deployment). Le tableau page-par-page qui le prouve :
**[`DOC-COVERAGE.md`](DOC-COVERAGE.md)**. Des **mini-projets** de validation jalonnent le
parcours : **[`projets/`](projets/)**.

---

## Rythme conseillé / Suggested pace

- **Intensif** : 1 module tous les 2–3 jours → ~4 semaines.
- **Régulier** : 1 module par semaine → ~3 mois.
- Ne saute pas les exercices. Un module « lu » n'est pas un module « acquis ».

---

## Démarrage rapide / Quickstart

```bash
git clone https://github.com/patrick26-Developer/Backend-Python.git
cd Backend-Python
```

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"

Copy-Item .env.example .env
fastapi dev taskman/main.py
# -> http://127.0.0.1:8000/docs
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"

cp .env.example .env
fastapi dev taskman/main.py
```

Détails, alternative `uv`, et outillage : [`00-setup/README.md`](00-setup/README.md).

---

## Conventions du dépôt

- **Langue** : titres et README bilingues FR/EN ; théorie en français, termes techniques en
  anglais (c'est le vocabulaire du métier — autant s'y habituer).
- **Style de code** : `ruff format` + `ruff check` + `mypy --strict`. Le code des `solutions/`
  passe le lint et le type-check.
- **Commits** : format [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

---

## Licence

MIT — voir [`LICENSE`](LICENSE). Utilise, forke, partage, enseigne.
