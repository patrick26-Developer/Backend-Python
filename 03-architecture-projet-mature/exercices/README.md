# Module 03 — Exercices

> On **refactore** `taskman` du Module 02 (un `main.py` + `models.py` + `store.py`) vers une
> architecture en couches. Objectif : **zéro changement de comportement**, tous les tests du
> Module 02 restent verts après migration.

**Filet de sécurité :**

```bash
git add -A && git commit -m "checkpoint: avant refactor module 03"
```

---

## Exercice 03.1 — Créer l'arborescence et déplacer les schémas 🟢

1. Crée l'arborescence :
   ```
   taskman/core/__init__.py       taskman/schemas/__init__.py
   taskman/repositories/__init__.py taskman/services/__init__.py
   taskman/api/__init__.py         taskman/api/routes/__init__.py
   ```
2. Déplace `taskman/models.py` → `taskman/schemas/task.py` (sans rien changer au contenu).
3. Fais de `taskman/schemas/__init__.py` un point d'entrée : il ré-exporte `TaskCreate`,
   `TaskRead`, etc. (`from taskman.schemas import TaskRead` doit marcher).
4. Corrige les imports dans `store.py` et `main.py`.

**Critères d'acceptation**
- [ ] `pytest` : tous les tests du Module 02 passent encore (après avoir corrigé leurs imports).
- [ ] `from taskman.schemas import TaskRead, TaskFilters` fonctionne.
- [ ] `ruff` + `mypy` OK.

---

## Exercice 03.2 — La couche repository (`Protocol` + implémentation) 🟡

1. `taskman/repositories/base.py` : un `Protocol` `TaskRepository` avec `create`, `get`,
   `list`, `update`, `delete` (mêmes signatures que ton `InMemoryTaskStore` actuel).
2. `taskman/repositories/memory.py` : renomme `InMemoryTaskStore` → `InMemoryTaskRepository`,
   déplace-le ici. Aucune logique ne change.
3. `taskman/repositories/__init__.py` : ré-exporte `TaskRepository` et `InMemoryTaskRepository`.
4. Vérifie avec mypy que `InMemoryTaskRepository` **satisfait** le `Protocol` **sans en
   hériter** : ajoute dans un fichier de test
   ```python
   def _check(r: TaskRepository) -> None: ...
   _check(InMemoryTaskRepository())   # mypy doit accepter
   ```

**Critères d'acceptation**
- [ ] `InMemoryTaskRepository` n'hérite PAS de `TaskRepository` mais mypy l'accepte comme tel.
- [ ] Changer une signature du `Protocol` fait échouer mypy sur l'implémentation.
- [ ] `ruff` + `mypy` OK.

---

## Exercice 03.3 — La couche service 🟡

1. `taskman/services/tasks.py` : `TaskService` avec un constructeur
   `__init__(self, tasks: TaskRepository)`.
2. Méthodes : `create`, `get`, `list` (renvoie un `TaskPage`), `update`, `delete`.
   Pour l'instant, elles **délèguent** au repository. `list` fait l'emballage `TaskPage`.
3. `grep -r "fastapi\|HTTPException\|Request" taskman/services/` doit ne **rien** renvoyer.
4. Écris `tests/unit/test_service.py` : teste `TaskService` avec un **faux** repository
   (une classe qui implémente le `Protocol`), **sans** `TestClient`.

**Critères d'acceptation**
- [ ] Le service ne connaît ni HTTP ni le repository concret (seulement le `Protocol`).
- [ ] `TaskService` est testé sans lancer d'app FastAPI.
- [ ] `list()` renvoie bien un `TaskPage` avec `total`.

---

## Exercice 03.4 — Configuration typée 🟡

1. `taskman/core/config.py` : `Settings(BaseSettings)` avec `env`, `name`, `version`,
   `host`, `port` (borné 1–65535), `log_level`. `env_prefix="APP_"`, `env_file=".env"`,
   `extra="ignore"`.
2. Propriétés `is_production` et `docs_url` (`None` en prod, `/docs` sinon).
3. `get_settings()` mémoïsé avec `@lru_cache`.
4. Mets à jour `.env.example` pour refléter les vraies variables (`APP_ENV`, `APP_LOG_LEVEL`…).
5. `grep -rn "os.environ\|getenv" taskman/` (hors `core/config.py`) → **rien**.

**Critères d'acceptation**
- [ ] `APP_PORT=abc` → l'app refuse de démarrer (erreur de validation claire).
- [ ] `Settings(env="production").docs_url is None`.
- [ ] Aucun `os.environ` hors de `core/config.py`.

---

## Exercice 03.5 — Routers, dépendances, `create_app` 🔴

1. `taskman/api/routes/meta.py` : router sans préfixe, routes `/` (injecte `Settings`) et
   `/health`.
2. `taskman/api/routes/tasks.py` : `APIRouter(prefix="/tasks", tags=["tasks"])` avec les 5
   routes CRUD. Chaque route reçoit le service via `Depends`.
3. `taskman/api/deps.py` :
   - `get_task_repository(request)` → `request.app.state.task_repository` ;
   - `get_task_service(repo=Depends(get_task_repository))` → `TaskService(repo)` ;
   - alias `TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]`.
4. `taskman/main.py` : `lifespan` qui met un `InMemoryTaskRepository()` dans
   `app.state.task_repository` ; `create_app(settings=None)` qui monte les 2 routers ;
   `app = create_app()`.
5. Les routes ne doivent **plus** contenir de logique ni d'accès direct au store.

**Critères d'acceptation**
- [ ] `fastapi dev taskman/main.py` démarre, `/docs` liste tout, comportement identique au Module 02.
- [ ] Aucune route ne référence `store` / le repository directement (tout passe par `service`).
- [ ] `create_app(Settings(env="test"))` renvoie une app utilisable en test.

---

## Exercice 03.6 — Tests via `dependency_overrides` 🔴

1. `tests/conftest.py` : une fixture `repository` (un `InMemoryTaskRepository` neuf) et une
   fixture `client` qui :
   - fabrique l'app via `create_app(Settings(env="test"))` ;
   - fait `app.dependency_overrides[get_task_repository] = lambda: repository` ;
   - `yield` un `TestClient` ;
   - `app.dependency_overrides.clear()` au teardown.
2. Adapte les tests d'intégration : ils utilisent la fixture `client`.
3. Ajoute un test qui prouve l'isolation : deux tests successifs ne partagent **pas** de
   données.
4. Ajoute un test qui prouve que la config injectée est bien celle des tests
   (`GET /` → `"env": "test"`).

**Critères d'acceptation**
- [ ] Aucune donnée ne « fuit » d'un test à l'autre (fixture `repository` neuve).
- [ ] Le test peut remplacer le repository par un faux sans toucher au code de prod.
- [ ] `pytest` 100 % déterministe.

---

## Rendu du module

```
taskman/
├── main.py
├── core/config.py
├── schemas/task.py
├── repositories/{base,memory}.py
├── services/tasks.py
└── api/{deps.py, routes/{meta,tasks}.py}
```

```bash
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "refactor(module-03): architecture en couches + DI + config typée"
```

Puis [`../solutions/README.md`](../solutions/) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).
