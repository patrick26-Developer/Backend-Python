# Module 03 — Architecture d'un projet mature

> **Objectif** : organiser la base de code pour qu'elle **scale en équipe et dans ta tête**.
> `taskman` passe d'un `main.py` unique à une **arborescence en couches** avec **injection de
> dépendances** et **configuration typée par environnement**.
>
> **Durée estimée** : 8 à 12 h.
> **Pré-requis** : Modules 01–02 terminés.

---

## 1. Pourquoi structurer ?

Un `main.py` de 300 lignes « marche ». Puis :

- 3 personnes veulent y toucher en même temps → conflits git permanents ;
- tu veux tester la logique métier sans lancer un serveur HTTP → impossible, tout est mélangé ;
- tu veux remplacer le store en mémoire par PostgreSQL → il faut réécrire les routes ;
- un nouveau arrive → il lui faut 3 jours pour comprendre où est quoi.

La structure n'est pas de la décoration : c'est ce qui rend le code **modifiable** à
plusieurs, **testable** par morceaux, et **compréhensible** par quelqu'un d'autre que toi.

> ⚠️ L'inverse est vrai aussi : **sur-structurer** un petit projet (10 dossiers pour 5
> routes) est une dette. On introduit une couche **quand son absence commence à faire mal**.
> Au Module 01, un fichier suffisait. Ici, on en a besoin.

---

## 2. L'architecture en couches

```
        HTTP  (requête)
          │
          ▼
┌───────────────────┐   api/routes/*.py
│      ROUTER       │   Traduit HTTP ↔ métier. Lit la requête, appelle le service,
│  (couche HTTP)    │   mappe le résultat sur un code de statut. RIEN d'autre.
└─────────┬─────────┘
          │  appelle
          ▼
┌───────────────────┐   services/*.py
│     SERVICE       │   La logique applicative : orchestration, règles métier,
│  (couche métier)  │   frontière transactionnelle (Module 04). Ne connaît NI HTTP NI SQL.
└─────────┬─────────┘
          │  utilise
          ▼
┌───────────────────┐   repositories/*.py
│   REPOSITORY      │   L'accès aux données. Une interface (Protocol) + N implémentations
│ (couche données)  │   (mémoire, SQL...). Ne connaît PAS le métier.
└─────────┬─────────┘
          │
          ▼
     Store / Base de données
```

### Qui a le droit de connaître quoi ?

| Couche | Connaît | Ne connaît PAS |
|---|---|---|
| **router** | HTTP, `Request`, `HTTPException`, les schémas, le service | le repository, le SQL |
| **service** | les schémas, le repository (via son interface), les règles métier | `fastapi`, `Request`, HTTP, le SQL concret |
| **repository** | les schémas, le stockage (dict, SQLAlchemy…) | le métier, HTTP |

**Test de la règle** : `grep -r "import fastapi" taskman/services/` doit ne **rien** renvoyer.
`grep -r "sqlalchemy" taskman/api/` non plus.

### Le flux, concrètement

```python
# api/routes/tasks.py  — couche HTTP
@router.get("/{task_id}")
def get_task(task_id: int, service: TaskServiceDep) -> TaskRead:
    task = service.get(task_id)          # appelle le métier
    if task is None:
        raise HTTPException(404, "Task not found")   # décision HTTP
    return task

# services/tasks.py  — couche métier
class TaskService:
    def get(self, task_id: int) -> TaskRead | None:
        return self._tasks.get(task_id)   # délègue au repository

# repositories/memory.py  — couche données
class InMemoryTaskRepository:
    def get(self, task_id: int) -> TaskRead | None:
        return self._items.get(task_id)
```

> **« Mais le service ne fait que déléguer ! »** Oui, pour l'instant. La couture (le fait que
> la route passe *toujours* par le service) est ce qui compte. Le service se remplit ensuite :
> transactions (M04), exceptions métier (M05), autorisation (M06), cache & événements (M08).
> Créer la couture maintenant coûte 10 minutes ; l'ajouter plus tard coûte un refactor.

---

## 3. `APIRouter` : découper les routes par domaine

```python
# api/routes/tasks.py
from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", status_code=201)      # -> POST /tasks
def create_task(...): ...

@router.get("/{task_id}")              # -> GET /tasks/{task_id}
def get_task(...): ...
```

```python
# main.py
from taskman.api.routes import meta, tasks

app.include_router(meta.router)
app.include_router(tasks.router)
```

- `prefix="/tasks"` : plus besoin de le répéter sur chaque route.
- `tags=["tasks"]` : regroupe dans `/docs`.
- `dependencies=[Depends(...)]` sur l'`APIRouter` : applique une dépendance à **toutes** les
  routes du router (ex. authentification — Module 06).
- Un router **par domaine** (`tasks`, `projects`, `auth`, `meta`…), un fichier par router.

C'est la recette officielle *« Bigger Applications - Multiple Files »*.

---

## 4. L'injection de dépendances (`Depends`)

### L'idée

Au lieu qu'une fonction **crée** ce dont elle a besoin, on le lui **fournit**. FastAPI résout
le graphe automatiquement.

```python
# api/deps.py
def get_task_repository(request: Request) -> TaskRepository:
    return request.app.state.task_repository        # créé au démarrage (lifespan)

def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(tasks)

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
```

```python
# api/routes/tasks.py
@router.get("")
def list_tasks(filters: Annotated[TaskFilters, Query()], service: TaskServiceDep) -> TaskPage:
    return service.list(filters)
```

FastAPI voit `service: TaskServiceDep` → appelle `get_task_service` → qui a besoin de
`get_task_repository` → qu'il appelle aussi. **Graphe résolu tout seul.**

### Pourquoi c'est LA fonctionnalité clé pour la testabilité

```python
# en test
app.dependency_overrides[get_task_repository] = lambda: fake_repo
```

Une ligne, et **toutes** les routes utilisent `fake_repo`. Pas de *monkeypatch*, pas de
variable globale à réinitialiser. C'est propre, local au test, réversible
(`app.dependency_overrides.clear()`).

### Les formes de dépendances

| Forme | Exemple | Usage |
|---|---|---|
| fonction | `Depends(get_settings)` | le cas courant |
| classe | `Depends(Paginator)` | dépendance avec des paramètres de requête à elle |
| sous-dépendance | une dépendance qui `Depends(...)` d'une autre | graphe (repo → service) |
| `dependencies=[...]` sur route/router | `@router.get(..., dependencies=[Depends(verify_token)])` | effet de bord (auth), pas de valeur retournée |
| dépendance globale | `FastAPI(dependencies=[...])` | s'applique à toute l'app |
| avec `yield` | ouvre/ferme une ressource (session DB) | Module 04 |

### `Depends` avec `yield` (aperçu, détaillé au Module 04)

```python
def get_session():
    session = SessionLocal()
    try:
        yield session          # <- fourni à la route
    finally:
        session.close()        # <- exécuté APRÈS la réponse, toujours
```

Le code après `yield` s'exécute à la fin de la requête (même en cas d'exception). C'est le
mécanisme des sessions de base de données.

---

## 5. Configuration typée : `pydantic-settings`

### Le problème

`os.environ["DATABASE_URL"]` éparpillé dans 12 fichiers → impossible de savoir ce que l'app
attend comme config, aucune validation, `KeyError` en pleine prod.

### La solution

```python
# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    name: str = "taskman"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- **une seule source de vérité** pour la config, **typée et validée** (un `APP_PORT=abc` →
  erreur au démarrage, pas à la 1ʳᵉ requête) ;
- **priorité** : arguments > variables d'environnement > `.env` > défauts ;
- `env_prefix="APP_"` : le champ `env` lit `APP_ENV`, `port` lit `APP_PORT`… ;
- `@lru_cache` : `Settings()` n'est lu qu'**une fois** (lire le disque/env à chaque requête
  serait absurde) ;
- `extra="ignore"` : les variables d'env non déclarées (`PATH`, `HOME`…) n'font pas planter.

### Config par environnement

```python
@property
def docs_url(self) -> str | None:
    return None if self.env == "production" else "/docs"   # /docs fermé en prod
```

Le **même artefact** (image Docker) tourne partout ; seule la config change (12-factor,
Module 09/11).

### Règle absolue

**Aucun `os.environ` en dehors de `core/config.py`.** Tout le reste reçoit `Settings` par
injection (`Depends(get_settings)`).

---

## 6. `lifespan` : ouvrir et fermer les ressources

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.task_repository = InMemoryTaskRepository()   # AU DÉMARRAGE
    yield
    # AU DÉMARRAGE : fermer le pool DB, flush des logs, etc.

app = FastAPI(lifespan=lifespan)
```

- le code **avant** `yield` : au démarrage de l'app (une fois).
- le code **après** `yield` : à l'arrêt propre (une fois).
- `app.state` : un espace pour ranger les objets partagés (pool DB, client HTTP, repo…).
- Module 04 : c'est ici qu'on crée `create_async_engine(...)`.

> Remplace les anciens `@app.on_event("startup"/"shutdown")` (dépréciés).

---

## 7. La fabrique d'application (`create_app`)

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.name, lifespan=lifespan, docs_url=settings.docs_url)
    app.include_router(meta.router)
    app.include_router(tasks.router)
    return app

app = create_app()      # pour `fastapi dev taskman/main.py`
```

Pourquoi une fonction plutôt qu'un `app = FastAPI()` au niveau module ?

- **tests** : `create_app(Settings(env="test"))` → une app configurée pour les tests, isolée ;
- **plusieurs configs** : staging vs prod sans dupliquer le code ;
- **pas d'effets de bord à l'import** : importer `taskman.main` ne doit pas ouvrir de
  connexion DB.

---

## 8. L'arborescence cible

```
taskman/
├── __init__.py
├── main.py                 # create_app(), lifespan
├── core/
│   ├── __init__.py
│   └── config.py           # Settings, get_settings
├── schemas/                # contrats Pydantic (ex-"models.py")
│   ├── __init__.py
│   └── task.py
├── repositories/           # accès données
│   ├── __init__.py
│   ├── base.py             # TaskRepository (Protocol)
│   └── memory.py           # InMemoryTaskRepository
├── services/               # logique métier
│   ├── __init__.py
│   └── tasks.py            # TaskService
└── api/                    # couche HTTP
    ├── __init__.py
    ├── deps.py             # get_task_repository, get_task_service...
    └── routes/
        ├── __init__.py
        ├── meta.py
        └── tasks.py
```

Règle de nommage : **par couche d'abord** (`api/`, `services/`, `repositories/`), **par
domaine ensuite** (`tasks.py`, `projects.py`). À grande échelle on inverse parfois (par
*feature*) — voir Module 12.

---

## 9. `Protocol` : l'interface du repository sans héritage

```python
from typing import Protocol

class TaskRepository(Protocol):
    def create(self, data: TaskCreate) -> TaskRead: ...
    def get(self, task_id: int) -> TaskRead | None: ...
    ...
```

- **typage structurel** : `InMemoryTaskRepository` **n'hérite pas** de `TaskRepository`.
  Il *est* un `TaskRepository` parce qu'il a les bonnes méthodes. mypy le vérifie.
- le service dépend de l'**interface**, pas de l'implémentation → on peut brancher
  `SqlAlchemyTaskRepository` (M04) sans toucher au service ni aux routes.
- c'est l'**inversion de dépendance** (le « D » de SOLID), version pythonique.

---

## 10. Pièges fréquents

1. **Logique métier dans la route** : `if task.status == "done" and ...:` n'a rien à faire
   dans une fonction `@router.get`. → service.
2. **`import fastapi` dans un service** : le signe que les couches fuient.
3. **`os.environ` hors de `config.py`**.
4. **`Settings()` appelé à chaque requête** : oublié le `@lru_cache`.
5. **`app = FastAPI()` au niveau module** avec effets de bord (connexion DB à l'import).
6. **Repository qui renvoie des entités ORM** au lieu de schémas → le SQL fuite dans les couches hautes (on gère ça au M04).
7. **Sur-découpage** : 6 fichiers pour 3 routes. La structure suit le besoin.
8. **Sous-dépendances non typées** : `Annotated[X, Depends(f)]` partout, pas `x = Depends(f)`.
9. **Oublier `app.dependency_overrides.clear()`** entre les tests → fuite d'état.
10. **Mettre `TaskFilters` / exemples OpenAPI dans `main.py`** : ça vit dans `schemas/` ou près du router.

---

## 11. Ce que `taskman` gagne dans ce module

- arborescence `core / schemas / repositories / services / api` ;
- `Settings` typé + `get_settings` mémoïsé, config par environnement (`/docs` fermé en prod) ;
- `TaskRepository` (Protocol) + `InMemoryTaskRepository` ;
- `TaskService` (mince mais réel — la couture est là) ;
- routers `meta` et `tasks` montés par `create_app` ;
- `lifespan` qui crée le repository dans `app.state` ;
- tests réorganisés : service testé **sans HTTP**, repository **remplacé** par override.

---

## 12. À savoir refaire sans aide

- Découper une API en `router / service / repository` et dire ce qui va où.
- Écrire un `Protocol` d'interface et une implémentation qui le satisfait (vérifié par mypy).
- Câbler un graphe de dépendances (`repo → service → route`) avec `Depends`.
- Remplacer une dépendance dans un test via `app.dependency_overrides`.
- Écrire un `Settings` `pydantic-settings` et l'injecter partout.
- Écrire un `lifespan` et une fabrique `create_app`.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
