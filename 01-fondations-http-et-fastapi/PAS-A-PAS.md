# Module 01 — Explication pas à pas du code

> Ce document explique la solution **ligne par ligne**. Objectif : qu'aucune ligne de
> `models.py`, `store.py` et `main.py` ne reste un mystère. Garde les fichiers ouverts
> à côté ([`solutions/`](solutions/)).

---

## Partie A — `solutions/models.py`

### En-tête

```python
from __future__ import annotations
```

Active l'évaluation **différée** des annotations (PEP 563). Concrètement : toutes les
annotations de type deviennent des chaînes de caractères, évaluées seulement si quelqu'un le
demande (mypy, Pydantic…). Deux bénéfices ici :

1. on peut écrire `-> TaskBase` **à l'intérieur** de la classe `TaskBase` sans erreur
   (la classe n'existe pas encore quand la ligne est lue) ;
2. c'est gratuit à l'exécution.

> ⚠️ Pydantic v2 sait résoudre ces annotations différées. Certains cas très avancés
> demandent `model_rebuild()` — on n'y est pas.

```python
from datetime import UTC, datetime
```

`datetime` : le type date-heure. `UTC` : l'objet fuseau horaire UTC (`datetime.timezone.utc`,
raccourci depuis Python 3.11). On s'en sert pour créer des dates **timezone-aware**.

```python
from enum import StrEnum
```

`StrEnum` (Python 3.11+) : une énumération dont **chaque membre est aussi une `str`**.
`TaskStatus.done == "done"` est `True`, et `json.dumps(TaskStatus.done)` donne `"done"`.
Idéal pour un champ d'API : validé côté entrée, lisible côté sortie, documenté comme `enum`
dans OpenAPI.

```python
from pydantic import BaseModel, Field, field_validator, model_validator
```

- `BaseModel` : la classe mère de tout schéma Pydantic (validation + (dé)sérialisation).
- `Field` : décrit finement un champ (contraintes, valeur par défaut, doc, exemple).
- `field_validator` : décorateur pour valider/normaliser **un** champ.
- `model_validator` : décorateur pour valider le modèle **entier** (relations entre champs).

### `TaskStatus`

```python
class TaskStatus(StrEnum):
    todo = "todo"
    doing = "doing"
    done = "done"
```

Trois valeurs autorisées pour le statut d'une tâche. Toute autre valeur en entrée →
`ValidationError` → HTTP 422. Le nom du membre (`todo`) et sa valeur (`"todo"`) sont
identiques par convention, mais c'est la **valeur** qui circule dans le JSON.

### `TaskBase`

```python
class TaskBase(BaseModel):
```

Le **socle commun** aux schémas d'entrée (`TaskCreate`) et de sortie (`Task`). On factorise
ici les champs *et* leurs validateurs pour ne pas les dupliquer.

```python
    title: str = Field(min_length=1, max_length=200, description="Titre de la tâche")
```

- `title: str` : champ obligatoire de type chaîne.
- `Field(...)` remplace la valeur par défaut et ajoute des **contraintes déclaratives** :
  - `min_length=1` : chaîne vide refusée ;
  - `max_length=200` : au-delà, refusé ;
  - `description=...` : apparaît dans `/docs` et `openapi.json`.

> Ces contraintes sont vérifiées **avant** ton validateur `_title_not_blank`. L'ordre :
> contraintes `Field` → `field_validator`.

```python
    description: str | None = None
```

Champ **optionnel** : type `str` **ou** `None`, valeur par défaut `None`. Le client peut
l'omettre ou envoyer `null`.

```python
    priority: int = Field(default=3, ge=1, le=5, description="1 = basse … 5 = critique")
```

Entier entre 1 et 5 (`ge` = *greater or equal*, `le` = *less or equal*), défaut `3`.
`priority=0` ou `priority=6` → 422.

```python
    due_date: datetime | None = Field(default=None, description="Échéance (UTC)")
```

Date d'échéance optionnelle. Pydantic **parse** automatiquement une chaîne ISO 8601
(`"2026-12-31T17:00:00Z"`) en `datetime`. Le `Z` final est reconnu comme UTC.

```python
    tags: list[str] = Field(default_factory=list, max_length=10)
```

- `list[str]` : une liste de chaînes.
- `default_factory=list` : la valeur par défaut est **produite à chaque instance** en
  appelant `list()`. **Jamais `= []`** : un littéral serait un objet unique partagé par
  toutes les instances → bug classique de mutation partagée.
- `max_length=10` sur une liste = nombre maximum d'éléments.

```python
    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v
```

- `@field_validator("title")` : « exécute cette fonction pour valider `title` ».
- `@classmethod` + `cls` : signature imposée par Pydantic v2 (le validateur appartient à la
  classe, pas à l'instance).
- `v: str` : la valeur du champ, déjà passée par `Field(min_length=1, ...)`.
- `v.strip()` : on enlève les espaces de début/fin.
- `if not v:` : une chaîne vide (`""`) est *falsy*. `"   "` devient `""` après `strip()` →
  on lève.
- `raise ValueError(...)` : Pydantic l'attrape et le transforme en erreur de validation
  propre (→ 422 côté API).
- `return v` : **on renvoie la valeur nettoyée** ; c'est elle qui est stockée. Un validateur
  peut donc *normaliser*, pas seulement vérifier.

```python
    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            t = tag.strip()
            if not (1 <= len(t) <= 20):
                raise ValueError(f"tag invalide : {tag!r} (1 à 20 caractères)")
            cleaned.append(t)
        return cleaned
```

Pour chaque tag : on *strip*, on vérifie la longueur (`1 <= len(t) <= 20`, écriture
« chaînée » pythonique), on rejette sinon. `{tag!r}` insère la représentation *repr* (avec
les guillemets) dans le message. On renvoie la liste nettoyée.

```python
    @model_validator(mode="after")
    def _due_date_in_future(self) -> TaskBase:
        if self.due_date is not None:
            now = datetime.now(self.due_date.tzinfo or UTC)
            if self.due_date < now:
                raise ValueError("la date d'échéance doit être dans le futur")
        return self
```

- `@model_validator(mode="after")` : s'exécute **après** que tous les champs individuels
  sont validés et l'objet construit. On a donc accès à `self` et à **tous** les champs — ce
  qu'un `field_validator` ne permet pas.
- `if self.due_date is not None:` : rien à vérifier si pas d'échéance.
- `datetime.now(self.due_date.tzinfo or UTC)` : on récupère « maintenant » dans **le même
  fuseau** que la date fournie (ou UTC par défaut). Comparer un datetime *aware* et un
  *naïf* lèverait `TypeError` — on l'évite.
- `if self.due_date < now:` : dans le passé → refus.
- `return self` : un `model_validator(mode="after")` doit renvoyer l'instance.

### Les schémas concrets

```python
class TaskCreate(TaskBase):
    """Corps de POST /tasks. Aucun champ 'serveur' accepté."""
```

Hérite de `TaskBase` **sans rien ajouter**. Pourquoi une classe alors ? Pour **nommer le
contrat** : la signature `def create_task(payload: TaskCreate)` dit exactement ce qu'on
accepte. Le jour où la création diverge de la lecture (Module 02+), on modifie ici sans
toucher à `Task`.

```python
class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_date: datetime | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    status: TaskStatus | None = None
```

Le schéma du `PATCH`. **Tous les champs sont optionnels** (`X | None = None`) : le client
n'envoie que ce qu'il veut changer. On hérite de `BaseModel` (pas de `TaskBase`) pour ne pas
rendre `title` obligatoire. On ajoute `status`, qu'on ne pouvait pas fixer à la création.

```python
    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        ...
```

Même règle que dans `TaskBase`, mais adaptée au cas `None` (champ absent = on ne touche pas).

```python
class Task(TaskBase):
    id: int
    status: TaskStatus = TaskStatus.todo
    created_at: datetime
    updated_at: datetime
```

Le schéma de **sortie** : tout `TaskBase` + les champs gérés par le serveur. `id`,
`created_at`, `updated_at` sont obligatoires (le serveur les fournit toujours) ; `status` a
un défaut.

```python
    model_config = {
        "json_schema_extra": {
            "examples": [ { ...un exemple complet... } ]
        }
    }
```

`model_config` configure le modèle. `json_schema_extra.examples` injecte un exemple **réel**
dans `/docs` — ça rend la doc utilisable tout de suite (bouton « Try it out » pré-rempli).

```python
class TaskPage(BaseModel):
    items: list[Task]
    total: int
    limit: int
    offset: int
```

Enveloppe de **réponse paginée**. `items` = la page courante ; `total` = le nombre total
d'éléments correspondant au filtre (utile au client pour afficher « page 2/7 »).

---

## Partie B — `solutions/store.py`

```python
from datetime import UTC, datetime
from operator import attrgetter
```

`attrgetter("priority")` renvoie une fonction qui, appliquée à un objet, retourne
`obj.priority`. Pratique et rapide comme clé de tri.

```python
from .models import Task, TaskCreate, TaskStatus, TaskUpdate
```

Import **relatif** (`.models` = le module `models` du même paquet). Fonctionne parce que
`solutions/` contient un `__init__.py`.

```python
SortKey = str  # "priority" | "-priority" | "created_at" | "-created_at"
```

Un **alias de type** pour se documenter. Ici `SortKey` = `str`, mais le commentaire précise
les valeurs attendues. (Au Module 02 on ferait un `Literal[...]`.)

```python
def _now() -> datetime:
    return datetime.now(UTC)
```

Toujours passer par cette fonction pour « maintenant ». Avantages : datetime *aware*
garanti, et **un seul point à *monkeypatcher*** dans les tests si besoin.

```python
def _sorted(rows: list[Task], sort: SortKey) -> list[Task]:
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in {"priority", "created_at"}:
        field, reverse = "priority", True
    rows.sort(key=attrgetter("created_at"))
    rows.sort(key=attrgetter(field), reverse=reverse)
    return rows
```

- fonction **au niveau module** (pas méthode) : ainsi `list[Task]` dans la signature
  désigne bien le type `list`, et non une éventuelle méthode `list` de la classe.
- `reverse = sort.startswith("-")` : le préfixe `-` signale un tri décroissant.
- `field = sort.lstrip("-")` : on retire le `-` pour garder le nom du champ.
- garde-fou : champ inconnu → on retombe sur `-priority`.
- **double tri** : Python trie de façon *stable*. On trie d'abord par clé **secondaire**
  (`created_at` croissant), puis par clé **principale**. Résultat : à priorité égale, les
  tâches les plus anciennes d'abord — ordre **déterministe**, indispensable pour des tests
  fiables.

```python
class InMemoryTaskStore:
    def __init__(self) -> None:
        self._items: dict[int, Task] = {}
        self._seq: int = 0
```

- `_items` : dictionnaire `id -> Task`. Le `_` = « privé par convention ».
- `_seq` : compteur pour générer les identifiants.

```python
    def clear(self) -> None:
        self._items.clear()
        self._seq = 0
```

Remise à zéro — utilisé par les *fixtures* de test pour isoler chaque cas.

```python
    def create(self, data: TaskCreate) -> Task:
        self._seq += 1
        now = _now()
        task = Task(
            id=self._seq,
            status=TaskStatus.todo,
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        self._items[task.id] = task
        return task
```

- `self._seq += 1` : nouvel identifiant (1, 2, 3…).
- `data.model_dump()` : convertit le `TaskCreate` en `dict` (`{"title": ..., "priority": ...}`).
- `**...` : on « déplie » ce dict comme arguments nommés du constructeur `Task`.
- on complète avec les champs serveur (`id`, `status`, dates).
- `Task(...)` **revalide** l'ensemble — filet de sécurité.
- on range dans `_items` et on renvoie l'objet.

```python
    def get(self, task_id: int) -> Task | None:
        return self._items.get(task_id)
```

`dict.get` renvoie `None` si la clé manque — pas d'exception. **Le store ne connaît pas
HTTP** : c'est la route qui transformera ce `None` en 404.

```python
    def list(self, *, status=None, min_priority=None, sort="-priority", limit=20, offset=0):
        rows = list(self._items.values())
        if status is not None:
            rows = [t for t in rows if t.status == status]
        if min_priority is not None:
            rows = [t for t in rows if t.priority >= min_priority]
        total = len(rows)
        rows = _sorted(rows, sort)
        return rows[offset : offset + limit], total
```

- `*,` : tous les arguments suivants sont **obligatoirement nommés** (`store.list(status=...)`,
  jamais `store.list("done")`). Ça évite les erreurs de position.
- on copie les valeurs dans une liste, on applique les filtres présents.
- `total = len(rows)` : compté **après filtrage, avant pagination**.
- `rows[offset : offset + limit]` : la tranche de la page.
- on renvoie **un tuple** `(page, total)`.

```python
    def update(self, task_id: int, changes: TaskUpdate) -> Task | None:
        current = self._items.get(task_id)
        if current is None:
            return None
        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current
        updated = current.model_copy(update={**patch, "updated_at": _now()})
        self._items[task_id] = updated
        return updated
```

- absent → `None` (→ 404 côté route).
- `model_dump(exclude_unset=True)` : **seuls les champs réellement fournis** par le client
  figurent dans `patch`. C'est LE point clé du PATCH :
  - `PATCH {}` → `patch == {}` → `if not patch:` → on renvoie l'existant inchangé ;
  - `PATCH {"status": "done"}` → `patch == {"status": "done"}` → seul le statut bouge.
- `current.model_copy(update=...)` : crée une **nouvelle** instance `Task` avec les champs
  remplacés (Pydantic v2, immutabilité douce). On bump `updated_at`.
- on remplace dans `_items`, on renvoie.

```python
    def delete(self, task_id: int) -> bool:
        return self._items.pop(task_id, None) is not None
```

`dict.pop(key, None)` retire et renvoie la valeur, ou `None` si absente. On renvoie donc
`True` si quelque chose a été supprimé, `False` sinon.

---

## Partie C — `solutions/main.py`

```python
from typing import Annotated, Literal
```

- `Annotated[T, meta]` : un type `T` **plus** des métadonnées. FastAPI lit ces métadonnées
  (`Query(...)`, `Path(...)`) pour savoir quoi faire. C'est la syntaxe recommandée.
- `Literal["a", "b"]` : type dont les seules valeurs valides sont celles listées.

```python
from fastapi import FastAPI, HTTPException, Path, Query, Response, status
```

- `FastAPI` : l'application.
- `HTTPException` : pour renvoyer une erreur HTTP immédiate.
- `Path`, `Query` : déclarent contraintes et doc sur les paramètres d'URL.
- `Response` : l'objet réponse, qu'on manipule pour les en-têtes / le corps vide.
- `status` : des constantes lisibles (`status.HTTP_201_CREATED` == `201`).

```python
from .models import Task, TaskCreate, TaskPage, TaskStatus, TaskUpdate
from .store import InMemoryTaskStore
```

Nos modules. La route ne connaît que des **schémas** et le **store**.

```python
app = FastAPI(
    title="taskman",
    version="0.1.0",
    summary="API de gestion de tâches — Module 01 (fondations)",
)
```

Crée l'application. `title`, `version`, `summary` alimentent `/docs` et `openapi.json`.

```python
store = InMemoryTaskStore()
```

**Échafaudage** : une instance unique au niveau module. Au Module 03, elle passe derrière
`Depends(get_store)` pour être remplaçable en test et par environnement.

```python
@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": "taskman", "version": "0.1.0", "docs": "/docs"}
```

- `@app.get("/")` : enregistre une *path operation* pour `GET /`.
- `tags=["meta"]` : regroupe la route sous « meta » dans `/docs`.
- `-> dict[str, str]` : le type de retour. FastAPI sérialise le `dict` en JSON et le
  documente.

```python
@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Sonde basique. Au Module 09 elle devient `/health` (liveness) + `/ready` (readiness).

```python
@app.get("/echo/{item_id}", tags=["playground"])
def echo(
    item_id: Annotated[int, Path(ge=1)],
    q: Annotated[str | None, Query(max_length=50)] = None,
    verbose: Annotated[bool, Query()] = False,
) -> dict[str, object]:
    payload: dict[str, object] = {"item_id": item_id, "q": q, "verbose": verbose}
    if verbose:
        payload["length"] = len(q) if q else 0
    return payload
```

- `item_id: Annotated[int, Path(ge=1)]` : `item_id` vient du **chemin** (il est dans
  `/echo/{item_id}`), doit être un `int >= 1`. `/echo/0` → 422.
- `q: Annotated[str | None, Query(max_length=50)] = None` : `q` n'est **pas** dans le
  chemin → c'est un **query param**. Optionnel (défaut `None`), max 50 caractères.
- `verbose: Annotated[bool, Query()] = False` : query booléen. `?verbose=true`,
  `?verbose=1` → `True`.
- `dict[str, object]` : valeurs de types hétérogènes (str, int, bool) → `object`.
- `len(q) if q else 0` : expression conditionnelle ; `q` peut être `None` ou `""`.

> Cette route est un bac à sable pédagogique. On la supprime une fois la mécanique
> *path/query* comprise.

```python
TaskId = Annotated[int, Path(ge=1, description="Identifiant de la tâche")]
```

Un **alias réutilisable** : au lieu de réécrire `Annotated[int, Path(ge=1)]` dans 3 routes,
on écrit `task_id: TaskId`. DRY, et la contrainte reste cohérente partout.

```python
@app.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate, response: Response) -> Task:
    task = store.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task
```

- `status_code=201` : **code de succès par défaut** de cette route (création).
- `payload: TaskCreate` : type = `BaseModel` → FastAPI lit le **corps JSON**, le valide,
  le documente. Corps invalide → 422 automatique.
- `response: Response` : en déclarant ce paramètre, FastAPI nous **injecte** l'objet
  réponse, qu'on peut modifier avant l'envoi.
- `response.headers["Location"] = ...` : convention REST — indiquer **où** trouver la
  ressource créée.
- `return task` : l'objet `Task` ; FastAPI le filtre/valide/sérialise selon `-> Task`.

```python
@app.get("/tasks", tags=["tasks"])
def list_tasks(
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    min_priority: Annotated[int | None, Query(ge=1, le=5)] = None,
    sort: Annotated[Literal["priority", "-priority", "created_at", "-created_at"], Query()] = "-priority",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaskPage:
    items, total = store.list(
        status=status_filter, min_priority=min_priority, sort=sort, limit=limit, offset=offset,
    )
    return TaskPage(items=items, total=total, limit=limit, offset=offset)
```

- `status_filter ... Query(alias="status")` : la variable Python s'appelle `status_filter`
  (pour ne pas masquer le module `status` importé), mais l'API expose `?status=done`.
  `alias` découple nom interne et nom public.
- `min_priority` : query optionnel borné 1–5.
- `sort: Literal[...]` : seules ces 4 chaînes sont acceptées ; toute autre → 422, et la
  liste apparaît comme menu déroulant dans `/docs`.
- `limit` borné 1–100 (défaut 20), `offset >= 0` (défaut 0) : garde-fous **anti-abus** —
  un client ne peut pas demander 10 millions de lignes.
- on délègue au store, on emballe dans `TaskPage`.

```python
@app.get("/tasks/{task_id}", tags=["tasks"])
def get_task(task_id: TaskId) -> Task:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
```

- `task_id: TaskId` : path param `>= 1`. `/tasks/-1` → **422** (pas 404 : l'entrée est mal
  formée, ce n'est pas « pas trouvé »).
- `store.get` renvoie `None` si absent → on lève `HTTPException(404, ...)`.
- `detail="Task not found"` : le corps sera `{"detail": "Task not found"}` (format FastAPI
  par défaut, unifié au Module 05).

```python
@app.patch("/tasks/{task_id}", tags=["tasks"])
def update_task(task_id: TaskId, changes: TaskUpdate) -> Task:
    task = store.update(task_id, changes)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
```

`PATCH` = modification **partielle**. `changes: TaskUpdate` (tous champs optionnels). Toute
la logique « ne changer que ce qui est fourni » est dans `store.update` (`exclude_unset`).

```python
@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: TaskId) -> Response:
    if not store.delete(task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- `status_code=204` : « OK, et pas de corps ».
- `store.delete` renvoie `False` si rien à supprimer → 404.
- `return Response(status_code=204)` : une réponse **explicitement vide**. On ne renvoie
  pas de `Task` — 204 interdit un corps.
- **Choix assumé** : un 2ᵉ `DELETE` sur le même id renvoie 404 (le client croyait la
  ressource là). 204 serait aussi valable (idempotence stricte). L'important : choisir,
  documenter, tester.

---

## Ce qu'on refactorera plus tard (et pourquoi c'est OK maintenant)

| Ici (Module 01) | Devient (module) | Raison |
|---|---|---|
| `store` global | `Depends(get_store)` (03) | testabilité, config par env |
| `raise HTTPException(404)` répété | exception métier + handler (05) | cohérence, routes plus fines |
| `InMemoryTaskStore` | `SqlAlchemyTaskRepository` (04) | vraie persistance |
| `def` | `async def` (04) | driver DB async |
| `Task` unique en sortie | `TaskRead` + champs calculés (02) | contrats précis |

**Principe** : on n'ajoute une abstraction que quand son absence commence à faire mal.
Introduire les couches maintenant, sans la douleur qui les motive, c'est du *cargo cult*.
