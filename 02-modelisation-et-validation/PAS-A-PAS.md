# Module 02 — Explication pas à pas du code

> On explique **chaque ligne nouvelle ou modifiée** par rapport au Module 01. Les bases
> (imports FastAPI, `@app.get`, `HTTPException`…) sont déjà couvertes dans
> [`../01-fondations-http-et-fastapi/PAS-A-PAS.md`](../01-fondations-http-et-fastapi/PAS-A-PAS.md).
> Garde [`solutions/`](solutions/) ouvert à côté.

---

## Partie A — `solutions/models.py`

### Imports

```python
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
```

- `Decimal` : type numérique **exact** (pas de représentation binaire flottante). Pour les
  montants, durées facturables, quantités précises.
- `Literal` : sert à définir `SortKey` (ensemble fermé de chaînes).

```python
from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field,
    computed_field, field_validator, model_validator,
)
```

- `ConfigDict` : la forme typée de `model_config` (mieux que le `dict` nu — mypy le comprend).
- `EmailStr` : type e-mail validé (nécessite `email-validator`, inclus dans `fastapi[standard]`).
- `computed_field` : expose une `@property` comme un champ (dans le JSON, dans OpenAPI).

### `SortKey`

```python
SortKey = Literal["priority", "-priority", "created_at", "-created_at", "due_date", "-due_date"]
```

Un **alias de type** : `SortKey` vaut exactement l'une de ces 6 chaînes. Utilisé dans
`TaskFilters.sort` et `store._sorted`. Toute autre valeur → 422 automatique + menu déroulant
dans `/docs`.

### `TaskStatus` — inchangé (voir Module 01)

### `ChecklistItem`

```python
class ChecklistItem(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    done: bool = False

    @field_validator("label")
    @classmethod
    def _label_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le label ne peut pas être vide")
        return v
```

Un modèle **imbriqué**. Dès qu'on écrit `checklist: list[ChecklistItem]` ailleurs, Pydantic
valide **chaque élément** avec ces règles, et un échec renvoie le **chemin exact**
(`body.checklist.2.label`). C'est tout l'intérêt vs valider une `list[dict]` à la main.

### `TaskBase` — champs enrichis, validateurs de **format uniquement**

```python
class TaskBase(BaseModel):
    title: str = Field(
        min_length=1, max_length=200,
        description="Titre de la tâche",
        examples=["Rédiger l'ADR sur le découpage en modules"],
    )
```

`examples=[...]` sur le `Field` : l'exemple apparaît dans `/docs` au niveau du champ. Une
doc avec exemples réalistes se prend en main 10× plus vite.

```python
    description: str | None = Field(default=None, max_length=5000)
```

On borne aussi les champs optionnels : sans `max_length`, un client peut envoyer 50 Mo de
texte. (Les limites de payload globales viennent au Module 10, mais borner au niveau champ
est gratuit.)

```python
    assignee_email: EmailStr | None = Field(default=None, examples=["dev@exemple.org"])
```

`EmailStr` : `"pas-un-email"` → 422. La validation est déléguée à `email-validator`
(RFC 5322 simplifiée).

```python
    estimate_hours: Decimal | None = Field(
        default=None, ge=0, max_digits=5, decimal_places=2, examples=["2.50"]
    )
```

- `Decimal` et non `float`.
- `max_digits=5` : au plus 5 chiffres significatifs (`999.99`).
- `decimal_places=2` : au plus 2 décimales. `"1.005"` → 422.
- `ge=0` : pas de durée négative.

```python
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=50)
```

Liste de modèles imbriqués, au plus 50 items, défaut = liste **neuve** à chaque instance.

```python
    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in tags:
            t = tag.strip().lower()          # <- normalisation : casse + espaces
            if not (1 <= len(t) <= 20):
                raise ValueError(f"tag invalide : {tag!r} (1 à 20 caractères)")
            cleaned.append(t)
        return cleaned
```

Nouveauté vs Module 01 : `.lower()`. `"Docs"` et `"docs"` deviennent le même tag → le
filtre `?tag=docs` est fiable.

> **Important** : `TaskBase` ne contient plus de `model_validator` « échéance future ».
> Voir la section suivante.

### `_ensure_future` — la règle métier, isolée

```python
def _ensure_future(due_date: datetime | None) -> None:
    if due_date is not None:
        now = datetime.now(due_date.tzinfo or UTC)
        if due_date < now:
            raise ValueError("la date d'échéance doit être dans le futur")
```

Fonction **au niveau module**, appelée par `TaskCreate` **et** `TaskUpdate`. Elle n'est
*pas* dans `TaskBase` → `TaskRead` (qui hérite de `TaskBase`) n'est **pas** soumis à cette
règle. Une tâche dont l'échéance est passée reste parfaitement lisible.

`datetime.now(due_date.tzinfo or UTC)` : on prend « maintenant » dans le **même fuseau** que
la date reçue pour éviter `TypeError: can't compare offset-naive and offset-aware`.

### `TaskCreate`

```python
class TaskCreate(TaskBase):
    project_id: int = Field(ge=1, description="Projet auquel rattacher la tâche")

    @model_validator(mode="after")
    def _due_date_in_future(self) -> TaskCreate:
        _ensure_future(self.due_date)
        return self
```

- `project_id` : **requis** (pas de défaut). Une tâche appartient toujours à un projet.
  Présent ici, absent de `TaskUpdate`.
- `@model_validator(mode="after")` : après construction, on applique la règle métier.
- `-> TaskCreate` + `return self` : signature imposée pour un validateur `after`.

### `TaskUpdate`

```python
class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_date: datetime | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    assignee_email: EmailStr | None = None
    estimate_hours: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=2)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=50)
    status: TaskStatus | None = None
```

Hérite de `BaseModel` (**pas** `TaskBase`) : sinon `title`, `project_id`… redeviendraient
obligatoires. **Tous** les champs sont `X | None = None` : le client n'envoie que ce qu'il
change. `status` apparaît (on ne pouvait pas le fixer à la création). `project_id` **n'y est
pas** (on ne déplace pas une tâche dans ce module).

```python
    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        return [t.strip().lower() for t in tags]
```

Version « nullable » du validateur : si `tags` n'est pas fourni (`None`), on ne fait rien.

```python
    @model_validator(mode="after")
    def _check_provided_fields(self) -> TaskUpdate:
        provided = self.model_fields_set
        if "title" in provided and self.title is None:
            raise ValueError("title ne peut pas être mis à null")
        if "due_date" in provided:
            _ensure_future(self.due_date)
        return self
```

- `self.model_fields_set` : l'ensemble des noms de champs **explicitement fournis** par le
  client (≠ champs à leur valeur par défaut).
- `"title" in provided and self.title is None` : le client a écrit `"title": null` → on
  refuse (422). S'il a **omis** `title`, `"title"` n'est pas dans `provided` → OK.
- `"due_date" in provided` : la règle « futur » ne s'applique que si le client a envoyé une
  `due_date`. `_ensure_future(None)` ne fait rien, donc `"due_date": null` (effacement) passe.

### `TaskRead`

```python
class TaskRead(TaskBase):
    model_config = ConfigDict(
        json_schema_extra={"examples": [ { ...exemple complet... } ]}
    )
    id: int
    project_id: int
    status: TaskStatus = TaskStatus.todo
    created_at: datetime
    updated_at: datetime
```

Tout `TaskBase` + les champs serveur. `project_id` est **ré-affiché** en sortie (utile de
savoir dans quel projet est la tâche). L'exemple complet alimente `/docs`.

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        if self.due_date is None or self.status is TaskStatus.done:
            return False
        return self.due_date < datetime.now(self.due_date.tzinfo or UTC)
```

- `@computed_field` : cette `@property` devient un champ **de sortie** (dans le JSON et dans
  le schéma OpenAPI de réponse), mais **pas** un champ d'entrée.
- `# type: ignore[prop-decorator]` : mypy n'aime pas l'empilement `computed_field` +
  `property` ; c'est le motif officiel Pydantic, l'ignore est volontaire.
- logique : en retard = a une échéance **passée** ET n'est **pas** `done`.
- `self.status is TaskStatus.done` : `is` fonctionne car `StrEnum` a des membres uniques
  (singletons).

### `TaskPage` — inchangé (items en `list[TaskRead]`)

### `TaskFilters`

```python
class TaskFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

`extra="forbid"` : un champ non déclaré dans la requête → `ValidationError` → 422. Sans ça
(défaut `ignore`), `?statuss=done` serait silencieusement ignoré et renverrait tout.

```python
    status: TaskStatus | None = None
    min_priority: int | None = Field(default=None, ge=1, le=5)
    project_id: int | None = Field(default=None, ge=1)
    q: str | None = Field(default=None, max_length=100, description="Recherche titre + description")
    sort: SortKey = "-priority"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

Filtres + tri + pagination, tous bornés. `limit ≤ 100` et `offset ≥ 0` sont des garde-fous
anti-abus (pas de « donne-moi 10 millions de lignes »).

---

## Partie B — `solutions/store.py`

```python
from taskman.models import (SortKey, TaskCreate, TaskFilters, TaskRead, TaskStatus, TaskUpdate)
```

Le store manipule désormais `TaskRead` (le modèle riche) en interne.

```python
def _sorted(rows: list[TaskRead], sort: SortKey) -> list[TaskRead]:
    reverse = sort.startswith("-")
    field = sort.lstrip("-")
    rows.sort(key=attrgetter("created_at"))                     # clé secondaire stable
    if field == "due_date":
        rows.sort(
            key=lambda t: (t.due_date is None, t.due_date or datetime.min.replace(tzinfo=UTC)),
            reverse=reverse,
        )
    else:
        rows.sort(key=attrgetter(field), reverse=reverse)
    return rows
```

- tri par `due_date` : la clé est un **tuple** `(t.due_date is None, <date>)`. Comme
  `False < True`, les tâches **avec** échéance passent avant celles **sans**, quel que soit
  le sens. `datetime.min.replace(tzinfo=UTC)` est un remplaçant *aware* pour comparer sans
  `TypeError`.
- double `sort()` : Python trie de façon **stable** → l'ordre secondaire (`created_at`) est
  préservé à valeur de clé principale égale. Résultat **déterministe** (tests fiables).

```python
    def create(self, data: TaskCreate) -> TaskRead:
        self._seq += 1
        now = _now()
        return self._put(
            TaskRead(
                id=self._seq, status=TaskStatus.todo,
                created_at=now, updated_at=now,
                **data.model_dump(),
            )
        )
```

`data.model_dump()` produit un `dict` de tous les champs de `TaskCreate` (dont `project_id`,
que `TaskRead` possède aussi). `**` les passe au constructeur. `_put` range et renvoie.

```python
    def list(self, filters: TaskFilters) -> tuple[list[TaskRead], int]:
        rows = list(self._items.values())
        if filters.status is not None:
            rows = [t for t in rows if t.status == filters.status]
        if filters.min_priority is not None:
            rows = [t for t in rows if t.priority >= filters.min_priority]
        if filters.project_id is not None:
            rows = [t for t in rows if t.project_id == filters.project_id]
        if filters.q:
            needle = filters.q.casefold()
            rows = [
                t for t in rows
                if needle in t.title.casefold()
                or (t.description is not None and needle in t.description.casefold())
            ]
        total = len(rows)
        rows = _sorted(rows, filters.sort)
        return rows[filters.offset : filters.offset + filters.limit], total
```

- **une seule** entrée : l'objet `filters`. La signature ne gonfle pas quand on ajoute un
  filtre.
- `if filters.q:` (et non `is not None`) : `""` est *falsy* → une recherche vide ne filtre
  rien.
- `.casefold()` : minuscule « agressive », meilleure que `.lower()` pour comparer sans
  tenir compte de la casse (gère mieux certaines langues).
- `total` compté **après filtres, avant pagination**.

```python
    def update(self, task_id: int, changes: TaskUpdate) -> TaskRead | None:
        current = self._items.get(task_id)
        if current is None:
            return None
        patch = changes.model_dump(exclude_unset=True)
        if not patch:
            return current
        data = current.model_dump()
        data.update(patch)
        data["updated_at"] = _now()
        return self._put(TaskRead.model_validate(data))
```

- `changes.model_dump(exclude_unset=True)` : **seuls** les champs explicitement fournis.
  `{}` → `patch` vide → on renvoie l'existant.
- `current.model_dump()` : l'état complet actuel en `dict` (les `ChecklistItem` deviennent
  des `dict`, `is_overdue` est inclus).
- `data.update(patch)` : on écrase les champs modifiés.
- `TaskRead.model_validate(data)` : **reconstruit et revalide tout** — les `dict` de
  `checklist` redeviennent des `ChecklistItem` validés ; `is_overdue` (présent dans `data`)
  est ignoré à l'entrée puis **recalculé**.
- on **ne** fait **pas** `current.model_copy(update=patch)` : `model_copy` ne valide pas,
  la checklist resterait des `dict`.

```python
    def _put(self, task: TaskRead) -> TaskRead:
        self._items[task.id] = task
        return task
```

Petit *helper* pour ranger + renvoyer en une expression (utilisé par `create` et `update`).

---

## Partie C — `solutions/main.py`

```python
from fastapi import Body, FastAPI, HTTPException, Path, Query, Response, status
```

`Body` en plus : pour attacher des exemples nommés au corps de `POST /tasks`.

```python
app = FastAPI(
    title="taskman", version="0.2.0",
    summary="...",
    separate_input_output_schemas=True,
)
```

`separate_input_output_schemas=True` est le **défaut** ; on l'écrit explicitement pour le
signaler. OpenAPI aura `TaskRead-Input` et `TaskRead-Output` distincts (utile aux
générateurs de SDK). Le passer à `False` fusionne les deux — à ne faire que si un outil
tiers l'exige.

```python
_CREATE_EXAMPLES = {
    "minimal": {"summary": "Minimal (champs requis seulement)",
                "value": {"title": "Acheter du café pour l'équipe", "project_id": 1}},
    "complet": {"summary": "Tous les champs", "value": { ... }},
}
```

Un `dict` d'exemples **nommés**. Chaque entrée a un `summary` (libellé du menu) et une
`value` (le corps pré-rempli).

```python
@app.post("/tasks", status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(
    payload: Annotated[TaskCreate, Body(openapi_examples=_CREATE_EXAMPLES)],
    response: Response,
) -> TaskRead:
    task = store.create(payload)
    response.headers["Location"] = f"/tasks/{task.id}"
    return task
```

- `Annotated[TaskCreate, Body(openapi_examples=...)]` : le corps reste un `TaskCreate`
  validé, **plus** un sélecteur d'exemples dans `/docs` (« minimal » / « complet »).
- reste identique au Module 01 : 201, en-tête `Location`, retour `TaskRead`.

```python
@app.get("/tasks", tags=["tasks"])
def list_tasks(filters: Annotated[TaskFilters, Query()]) -> TaskPage:
    items, total = store.list(filters)
    return TaskPage(items=items, total=total, limit=filters.limit, offset=filters.offset)
```

`Annotated[TaskFilters, Query()]` : FastAPI **éclate** le modèle en query params individuels
(`?status=&min_priority=&q=&sort=&limit=&offset=`), les valide via `TaskFilters`, et rejette
tout paramètre inconnu (`extra="forbid"`). La signature tient sur une ligne.

Les routes `GET /tasks/{id}`, `PATCH`, `DELETE` sont **identiques** au Module 01 (seul le
type de retour est passé de `Task` à `TaskRead`).

---

## Ce qu'on refactorera au Module 03

| Ici (Module 02) | Devient (Module 03) |
|---|---|
| `store` global | `Depends(get_repository)` |
| logique de filtrage dans `store.list` | reste, mais le store devient un vrai `repository` derrière une interface `Protocol` |
| `main.py` monolithique | `api/routes/tasks.py` via `APIRouter` |
| `TaskFilters`, `_CREATE_EXAMPLES` dans `main.py` | déplacés dans `schemas/` |
