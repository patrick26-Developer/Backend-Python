# Module 03 — Explication pas à pas du code

> On parcourt **chaque fichier** de la nouvelle arborescence. Le contenu des schémas
> (`schemas/task.py`) est celui du Module 02 — voir
> [`../02-modelisation-et-validation/PAS-A-PAS.md`](../02-modelisation-et-validation/PAS-A-PAS.md).
> Garde [`solutions/taskman/`](solutions/taskman/) ouvert.

Ordre de lecture recommandé (du bas de la pile vers le haut) :
**config → schemas → repositories → services → api/deps → api/routes → main**.

---

## 1. `taskman/core/config.py`

```python
from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
```

- `lru_cache` : mémoïsation (voir plus bas).
- `pydantic_settings` : l'extension de Pydantic qui lit variables d'env + `.env`.

```python
Environment = Literal["local", "test", "staging", "production"]
```

Alias de type : une `Environment` est **exactement** l'une de ces 4 chaînes.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

- `BaseSettings` : comme `BaseModel`, mais les valeurs peuvent venir de l'environnement.
- `env_file=".env"` : si le fichier existe, il est lu.
- `env_prefix="APP_"` : le champ `env` est alimenté par `APP_ENV`, `port` par `APP_PORT`…
  Le préfixe évite les collisions (`PATH`, `HOME`…).
- `extra="ignore"` : les variables d'env non déclarées ici ne font **pas** planter (sinon,
  `PATH` étant présent, l'app refuserait de démarrer).

```python
    env: Environment = "local"
    name: str = "taskman"
    version: str = "0.3.0"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
```

Chaque champ a un **défaut** → l'app démarre sans aucune variable d'env. `port` est **borné**
(un `APP_PORT=70000` → erreur de validation immédiate, pas un bug réseau obscur plus tard).

```python
    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def docs_url(self) -> str | None:
        return None if self.is_production else "/docs"
```

Des propriétés **dérivées** de la config. `docs_url` vaut `None` en prod → FastAPI **désactive**
`/docs`. Le comportement change avec l'environnement, pas avec le code.

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- `@lru_cache` sans argument : `get_settings()` n'exécute `Settings()` (= lire `.env`, parser,
  valider) **qu'une fois**. Tous les appels suivants renvoient le même objet.
- c'est **cette fonction** qu'on injecte (`Depends(get_settings)`), et qu'on surcharge en test.

---

## 2. `taskman/schemas/` — inchangé (Module 02), juste déplacé

`schemas/task.py` = l'ancien `models.py`. `schemas/__init__.py` **ré-exporte** pour que le
reste du code écrive `from taskman.schemas import TaskRead` sans connaître le sous-module :

```python
from taskman.schemas.task import (ChecklistItem, SortKey, TaskCreate, TaskFilters,
                                  TaskPage, TaskRead, TaskStatus, TaskUpdate)
__all__ = [...]
```

`__all__` : la liste publique du paquet (ce que `from taskman.schemas import *` exporterait,
et ce que les outils considèrent comme l'API du module).

---

## 3. `taskman/repositories/base.py`

```python
from typing import Protocol
from taskman.schemas import TaskCreate, TaskFilters, TaskRead, TaskUpdate

class TaskRepository(Protocol):
    def create(self, data: TaskCreate) -> TaskRead: ...
    def get(self, task_id: int) -> TaskRead | None: ...
    def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]: ...
    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None: ...
    def delete(self, task_id: int) -> bool: ...
```

- `Protocol` : définit une **forme**, pas une classe à hériter. Toute classe qui possède ces
  5 méthodes avec ces signatures **est** un `TaskRepository` aux yeux de mypy.
- `...` (Ellipsis) : corps vide, on ne décrit que la signature.
- ce fichier ne dépend que des **schémas** — jamais de `fastapi`, jamais d'un moteur SQL.

---

## 4. `taskman/repositories/memory.py`

Le contenu est l'ancien `store.py` (Module 02), classe renommée `InMemoryTaskStore` →
`InMemoryTaskRepository`. Points déjà expliqués au Module 02 :
`_sorted`, `create`, `list(filters)`, `update` via `model_validate`, `_put`.

```python
class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._items: dict[int, TaskRead] = {}
        self._seq: int = 0

    def clear(self) -> None: ...
```

**Aucune** mention de `TaskRepository` : la classe ne l'importe pas, n'en hérite pas. Elle le
*satisfait* structurellement. C'est mypy (et le test `_check`) qui garantit la conformité.

`clear()` n'est pas dans le `Protocol` : c'est un utilitaire propre à l'implémentation
mémoire (remise à zéro entre tests). Le `Protocol` ne liste que ce dont le **service** a
besoin.

---

## 5. `taskman/services/tasks.py`

```python
from taskman.repositories import TaskRepository
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate

class TaskService:
    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks
```

- le constructeur reçoit **un `TaskRepository`** (l'interface). Pas un
  `InMemoryTaskRepository`. Le service ne sait pas — et n'a pas à savoir — comment les
  données sont stockées.
- `self._tasks` : la dépendance, rangée en privé.

```python
    def create(self, data: TaskCreate) -> TaskRead:
        return self._tasks.create(data)

    def get(self, task_id: int) -> TaskRead | None:
        return self._tasks.get(task_id)

    def list(self, filters: TaskFilters) -> TaskPage:
        items, total = self._tasks.list(filters)
        return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)

    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        return self._tasks.update(task_id, changes)

    def delete(self, task_id: int) -> bool:
        return self._tasks.delete(task_id)
```

- `create`, `get`, `update`, `delete` : délégation pure **pour l'instant**.
- `list` : la seule qui fait quelque chose — l'**emballage** `(items, total)` → `TaskPage`.
  C'est une décision *applicative* (la forme de la réponse), donc c'est ici, pas dans le
  repository (qui reste bas niveau) ni dans la route (qui ne fait que du HTTP).

**Aucun** `import fastapi`. Aucun `HTTPException`. Le `None` de `get`/`update` est traduit en
404 **par la route**, pas ici (ça changera au Module 05).

---

## 6. `taskman/api/deps.py`

```python
from fastapi import Depends, Request
from taskman.core.config import Settings, get_settings
from taskman.repositories import TaskRepository
from taskman.services import TaskService

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

`SettingsDep` : un **alias**. Écrire `settings: SettingsDep` dans une route = « injecte-moi
la config ». Plus court et cohérent que répéter `Annotated[Settings, Depends(get_settings)]`.

```python
def get_task_repository(request: Request) -> TaskRepository:
    repo: TaskRepository = request.app.state.task_repository
    return repo
```

- `request: Request` → FastAPI injecte l'objet requête.
- `request.app.state.task_repository` → l'objet rangé au démarrage (voir `main.py`).
- l'annotation `repo: TaskRepository` documente et fait vérifier le type par mypy
  (`app.state` est dynamique, mypy ne connaît pas son contenu — on l'annonce).

```python
def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(tasks)
```

Une **sous-dépendance** : `get_task_service` a besoin du résultat de `get_task_repository`.
FastAPI appelle les deux, dans l'ordre. C'est le graphe de dépendances.

```python
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
```

L'alias qu'utiliseront toutes les routes de tâches.

---

## 7. `taskman/api/routes/meta.py`

```python
from fastapi import APIRouter
from taskman import __version__
from taskman.api.deps import SettingsDep

router = APIRouter(tags=["meta"])
```

`APIRouter` **sans** `prefix` : ces routes sont à la racine (`/`, `/health`). `tags=["meta"]`
les regroupe dans `/docs`.

```python
@router.get("/")
def root(settings: SettingsDep) -> dict[str, str]:
    return {"name": settings.name, "version": __version__, "env": settings.env, "docs": "/docs"}
```

`settings: SettingsDep` → la config est **injectée**. La route ne fait pas `get_settings()`
elle-même (ce serait un couplage dur et non surchargeable).

```python
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Liveness minimale. Le `/ready` (vérifie la DB, Redis…) arrive au Module 09.

---

## 8. `taskman/api/routes/tasks.py`

```python
from taskman.api.deps import TaskServiceDep
from taskman.schemas import TaskCreate, TaskFilters, TaskPage, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])
TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]
```

- `prefix="/tasks"` : les chemins deviennent `""` → `/tasks`, `"/{task_id}"` → `/tasks/{id}`.
- `_CREATE_EXAMPLES` : le `dict` d'exemples OpenAPI (Module 02), **déplacé ici** — près du
  router qui l'utilise, plus dans `main.py`.

```python
@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: Annotated[TaskCreate, Body(openapi_examples=_CREATE_EXAMPLES)],
    service: TaskServiceDep,
    response: Response,
) -> TaskRead:
    task = service.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task
```

- `@router.post("")` (chaîne vide) + `prefix="/tasks"` → `POST /tasks`.
- `service: TaskServiceDep` : le service est **injecté**. La route ne le construit pas.
- corps de la route : 3 lignes, **zéro logique**. Appelle le service, pose l'en-tête, renvoie.

```python
@router.get("")
def list_tasks(filters: Annotated[TaskFilters, Query()], service: TaskServiceDep) -> TaskPage:
    return service.list(filters)
```

Une ligne. `filters` (query model) validé par FastAPI, `service` injecté, on délègue.

```python
@router.get("/{task_id}")
def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    task = service.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
```

La **seule** responsabilité « intelligente » de la route : traduire `None` (métier) en
`404` (HTTP). Les routes `patch` et `delete` suivent le même patron.

---

## 9. `taskman/main.py`

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from taskman.api.routes import meta, tasks
from taskman.core.config import Settings, get_settings
from taskman.repositories import InMemoryTaskRepository
```

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.task_repository = InMemoryTaskRepository()
    yield
```

- `@asynccontextmanager` : transforme la fonction en gestionnaire de contexte async.
- **avant `yield`** : exécuté **une fois** au démarrage → on crée le repository et on le range
  dans `app.state`.
- **après `yield`** : exécuté **une fois** à l'arrêt propre → rien pour l'instant (Module 04 :
  `await engine.dispose()`).
- `AsyncIterator[None]` : le type de retour d'un `asynccontextmanager` qui ne « yield » rien
  d'utile.

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    override = settings is not None
    settings = settings or get_settings()
```

- `settings` optionnel : `None` → on prend la config globale (`get_settings()`). Fourni →
  on l'utilise (tests, scénarios).
- `override` : mémorise si un `settings` explicite a été passé.

```python
    app = FastAPI(
        title=settings.name,
        version=__version__,
        summary="...",
        lifespan=lifespan,
        docs_url=settings.docs_url,
        redoc_url=None if settings.is_production else "/redoc",
    )
```

L'app est **configurée depuis `settings`** : titre, docs ouvertes ou non selon l'env.

```python
    if override:
        app.dependency_overrides[get_settings] = lambda: settings
```

**Le point subtil.** Si on a passé un `settings` explicite, on force **aussi** la dépendance
`get_settings` à le renvoyer. Sans ça, `create_app(Settings(env="test"))` donnerait un app
au titre « test » mais des routes qui voient toujours l'env `local`. On aligne les deux.

```python
    app.include_router(meta.router)
    app.include_router(tasks.router)
    return app

app = create_app()
```

- `include_router` : monte chaque router sur l'app. L'ordre n'a pas d'importance ici.
- `app = create_app()` au niveau module : nécessaire pour `fastapi dev taskman/main.py`
  (la CLI cherche un objet `app`). L'import de `taskman.main` ne fait **aucune** I/O
  (le repository n'est créé qu'au `lifespan`, pas à l'import).

---

## 10. Les tests (`solutions/conftest.py` + `test_solution.py`)

```python
@pytest.fixture
def repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()          # NEUF à chaque test -> isolation
```

```python
@pytest.fixture
def client(repository):
    app = create_app(Settings(env="test"))
    app.dependency_overrides[get_task_repository] = lambda: repository
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- `create_app(Settings(env="test"))` : une app isolée, config de test.
- `dependency_overrides[get_task_repository] = lambda: repository` : **toutes** les routes
  utiliseront le repository de la fixture (neuf), pas celui du `lifespan`.
- `with TestClient(app)` : déclenche le `lifespan` (démarrage/arrêt).
- `.clear()` au teardown : on nettoie, pas de fuite vers le test suivant.

```python
def test_service_uses_any_repository_protocol() -> None:
    service = TaskService(InMemoryTaskRepository())
    ...
```

Le service se teste **sans app, sans HTTP** : on lui passe un repository, on appelle ses
méthodes. C'est tout le bénéfice du découpage.

---

## Ce qui change au Module 04

| Ici (Module 03) | Module 04 |
|---|---|
| `TaskRepository` sync | `TaskRepository` **async** (migration expliquée) |
| `InMemoryTaskRepository` dans `app.state` | `create_async_engine` + `async_sessionmaker` dans le `lifespan` |
| `get_task_repository` lit `app.state` | `get_session` (`Depends` avec `yield`) + repository construit sur la session |
| routes `def` | routes `async def` |
| service = délégation | service = **frontière transactionnelle** (`commit`/`rollback`) |
