# Module 03 — Solutions : les choix de conception

> Code dans `taskman/` (arborescence complète). Explication ligne par ligne :
> [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
cd 03-architecture-projet-mature/solutions
pytest          # tests de l'architecture
mypy taskman    # --strict
```

---

## Décision 1 — 3 couches, même quand le service « ne fait rien »

Le `TaskService` du Module 03 se contente de déléguer au repository. Beaucoup diraient
« couche inutile ». **Non** :

- la **couture** (route → service → repository, jamais route → repository) est ce qui a de
  la valeur. Elle est gratuite à créer maintenant, coûteuse à insérer plus tard.
- dès le Module 04, le service devient la **frontière transactionnelle** (`commit`/`rollback`).
- Module 05 : il lève `TaskNotFoundError` (le `None` disparaît).
- Module 06 : il vérifie `task.owner_id == current_user.id`.
- Module 08 : il gère le cache et émet des événements.

On ne construit pas la couche « au cas où » : on sait *exactement* ce qui va y arriver, et
c'est imminent.

## Décision 2 — `TaskRepository` est un `Protocol`, pas une classe de base

```python
class TaskRepository(Protocol):
    def get(self, task_id: int) -> TaskRead | None: ...
```

`InMemoryTaskRepository` **n'hérite pas** de `TaskRepository`. mypy vérifie *structurellement*
qu'il a les bonnes méthodes. Avantages :

- pas de couplage à une hiérarchie ;
- on peut faire d'un objet tiers un `TaskRepository` sans le modifier ;
- le service dépend de l'**abstraction**, jamais du concret → `SqlAlchemyTaskRepository`
  (M04) se branchera sans toucher au service ni aux routes.

Le test `test_service.py` crée un `FakeTaskRepository` maison : il « est » un
`TaskRepository` juste en ayant les méthodes.

## Décision 3 — Le repository vit dans `app.state`, injecté via `Request`

```python
# lifespan (main.py)
app.state.task_repository = InMemoryTaskRepository()

# deps.py
def get_task_repository(request: Request) -> TaskRepository:
    return request.app.state.task_repository
```

Pourquoi pas un simple global `repo = InMemoryTaskRepository()` dans `deps.py` ?

- `app.state` est **lié au cycle de vie de l'app** : recréé à chaque `create_app`, donc
  chaque app de test a le sien → isolation naturelle.
- au Module 04, `app.state` portera le moteur DB et le `sessionmaker`, ouverts dans le
  `lifespan` et fermés proprement à l'arrêt.
- `get_task_repository` reste **surchargable** en test (`dependency_overrides`).

## Décision 4 — `get_task_service` dépend de `get_task_repository`

```python
def get_task_service(
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(tasks)
```

FastAPI résout le graphe : route → `get_task_service` → `get_task_repository`. En test, on
surcharge **le maillon le plus bas** (`get_task_repository`) et tout le reste s'adapte. On
n'a jamais besoin de surcharger `get_task_service`.

## Décision 5 — `create_app(settings)` surcharge aussi `get_settings`

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    override = settings is not None
    settings = settings or get_settings()
    app = FastAPI(title=settings.name, ...)
    if override:
        app.dependency_overrides[get_settings] = lambda: settings
    ...
```

Sans la ligne `dependency_overrides[get_settings]`, `create_app(Settings(env="test"))`
configurerait le **titre** de l'app en mode test, mais la route `GET /` (qui fait
`Depends(get_settings)`) recevrait quand même le `get_settings()` **global** (env `local`).
Incohérent. On force donc la config injectée à s'appliquer **partout**.

C'est un piège classique de la DI : « configurer l'objet » ≠ « configurer ses dépendances ».

## Décision 6 — `@lru_cache` sur `get_settings`

Lire `.env` + parser + valider à **chaque requête** serait un gaspillage pur. `@lru_cache`
sans argument : la fonction n'est exécutée qu'une fois, le résultat est réutilisé. En test,
`Settings(_env_file=None)` contourne le cache en instanciant directement.

## Décision 7 — `docs_url` piloté par la config

```python
@property
def docs_url(self) -> str | None:
    return None if self.is_production else "/docs"
```

`/docs` et `/redoc` **fermés en production** (surface d'attaque réduite, on ne publie pas le
schéma interne). Le **même code** tourne partout ; seule `APP_ENV` change. Principe 12-factor
(Module 09).

---

## Grille d'auto-évaluation

- [ ] `grep -r "import fastapi" taskman/services taskman/repositories` → **vide** ?
- [ ] `grep -rn "os.environ" taskman/` (hors `core/config.py`) → **vide** ?
- [ ] Tes routes contiennent-elles encore un `if`/`for` de logique métier ?
- [ ] Peux-tu tester `TaskService` **sans** `TestClient` ?
- [ ] `create_app(Settings(env="test"))` : `GET /` renvoie-t-il `"env": "test"` ?
- [ ] Ton `InMemoryTaskRepository` hérite-t-il du `Protocol` (❌) ou le satisfait-il structurellement (✅) ?

➡️ [Module 04 — Bases de données](../../04-bases-de-donnees/THEORIE.md)
