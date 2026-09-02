# Module 02 — Modélisation & validation des données

> **Objectif** : concevoir des **contrats d'API explicites, impossibles à mal utiliser**.
> Ce qui entre, ce qui est stocké et ce qui sort sont **trois choses distinctes**.
>
> **Durée estimée** : 6 à 10 h.
> **Pré-requis** : Module 01 terminé, `taskman` avec CRUD en mémoire.

---

## 1. Le problème central : le contrat de données

La majorité des bugs d'API ne sont pas des bugs d'algorithme. Ce sont des bugs de
**contrat** :

- le client envoie un champ qu'il ne devrait pas pouvoir fixer (`id`, `owner_id`, `is_admin`) ;
- l'API renvoie un champ qu'elle ne devrait pas exposer (`password_hash`, `internal_notes`) ;
- un `PATCH` remet un champ à `null` alors que le client voulait juste ne pas y toucher ;
- un champ « optionnel » côté lecture devient « obligatoire » côté création, et le même
  modèle sert aux deux → incohérence.

La parade : **un schéma par usage**, et Pydantic pour rendre chaque règle *déclarative* et
*vérifiée*.

---

## 2. Séparer `Create` / `Update` / `Read` (et quand ne pas le faire)

### Le trio de base

```python
class TaskBase(BaseModel):          # champs communs + validateurs
    title: str
    description: str | None = None
    priority: int = 3

class TaskCreate(TaskBase):          # ENTRÉE création — POST
    project_id: int                 # requis à la création

class TaskUpdate(BaseModel):         # ENTRÉE modification — PATCH
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    status: TaskStatus | None = None

class TaskRead(TaskBase):            # SORTIE — ce que l'API renvoie
    id: int
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    is_overdue: bool                 # champ CALCULÉ, jamais reçu du client
```

**Règles :**

| Schéma | Hérite de | Contient |
|---|---|---|
| `*Base` | `BaseModel` | champs partagés + validateurs partagés |
| `*Create` | `*Base` | + champs requis seulement à la création |
| `*Update` | `BaseModel` (pas `*Base` !) | **tous** les champs en `X \| None = None` |
| `*Read` | `*Base` | + champs serveur (`id`, dates, calculés) |

`*Update` n'hérite **pas** de `*Base` : sinon `title` resterait obligatoire.

### Quand un seul modèle suffit

- objet de configuration interne jamais exposé sur le réseau ;
- prototype jetable ;
- ressource *read-only* (pas de `Create`/`Update` du tout).

Dès qu'il y a `POST` **et** `GET` sur une ressource métier : sépare. Le surcoût (3 classes
courtes) est négligeable devant le coût d'un modèle fourre-tout qu'on éclate plus tard dans
la douleur.

### La question officielle : « Separate schemas for input and output or not ? »

FastAPI ≥ 0.100 génère par défaut **deux schémas OpenAPI distincts** (`-Input` / `-Output`)
quand un champ a une valeur par défaut. Tu peux forcer un schéma unique avec
`FastAPI(separate_input_output_schemas=False)`. En pratique : **laisse le défaut**, la
distinction est utile aux générateurs de clients.

---

## 3. `response_model` / type de retour : le contrat de sortie

L'annotation de retour **est** le filtre de sortie.

```python
@app.get("/tasks/{id}")
def get_task(id: int) -> TaskRead:
    task = repo.get(id)          # objet potentiellement plus riche
    return task                  # FastAPI ne renvoie QUE les champs de TaskRead
```

FastAPI, à partir de ce type :

1. **filtre** : les champs absents de `TaskRead` sont retirés (protection anti-fuite) ;
2. **valide** : si `task` ne respecte pas `TaskRead`, erreur serveur explicite (bug attrapé) ;
3. **documente** la réponse dans `/docs`.

### `response_model` vs annotation de retour

```python
@app.get("/tasks/{id}", response_model=TaskRead)   # forme historique
def get_task(id: int) -> Task: ...                  # le type réel retourné

@app.get("/tasks/{id}")
def get_task(id: int) -> TaskRead: ...              # forme moderne, préférée
```

Utilise `response_model=` seulement quand le type retourné diffère du modèle public
(ex. tu renvoies une `Response` directe, ou un type ORM).

### Options utiles

```python
@app.get("/tasks", response_model_exclude_unset=True)   # n'émet que les champs réellement définis
@app.get("/me",   response_model_exclude={"internal_id"})
@app.get("/me",   response_model_include={"id", "email"})
```

- `response_model_exclude_unset` : utile pour des réponses « légères » (ne pas renvoyer les
  `null` et défauts non touchés).
- `exclude` / `include` : masquage ponctuel. Pour du récurrent, **fais un vrai schéma**.

### Modèles multiples pour une même entité (`Extra Models`)

Cas classique : `UserIn` (avec `password`), `UserOut` (sans), `UserInDB` (avec
`hashed_password`). On ne fait **jamais** transiter `password` en sortie. Techniques pour
factoriser : héritage (`UserBase`), ou `UserIn.model_dump()` + `**` vers `UserInDB`.

---

## 4. Validation : les 4 niveaux

Du plus simple au plus puissant :

### 4.1 Le type lui-même

```python
priority: int          # "abc" -> 422 ; "3" -> 3 (coercition)
done: bool             # "true"/1/"yes" -> True
due_date: datetime     # "2026-12-31T17:00:00Z" -> datetime aware
tags: list[str]        # {"a": 1} -> 422
```

### 4.2 Les contraintes `Field`

```python
title: str = Field(min_length=1, max_length=200)
priority: int = Field(ge=1, le=5)                 # ge/gt/le/lt
ratio: float = Field(gt=0, lt=1)
tags: list[str] = Field(max_length=10, min_length=0)
code: str = Field(pattern=r"^[A-Z]{3}-\d{4}$")
count: int = Field(multiple_of=5)
```

### 4.3 `field_validator` — un champ, logique custom

```python
from pydantic import field_validator

@field_validator("title")
@classmethod
def strip_title(cls, v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("titre vide")
    return v          # <- renvoie la valeur NORMALISÉE
```

Modes : `mode="before"` (avant coercition, `v` est brut) / `mode="after"` (défaut, `v` est
déjà du bon type). Plusieurs champs : `@field_validator("a", "b", "c")`.

### 4.4 `model_validator` — plusieurs champs ensemble

```python
from pydantic import model_validator

@model_validator(mode="after")
def check_dates(self) -> "Task":
    if self.start and self.end and self.start > self.end:
        raise ValueError("start doit précéder end")
    return self
```

`mode="before"` reçoit le `dict` brut ; `mode="after"` reçoit l'instance construite.

### Ordre d'exécution

```
before field_validators → coercition de type → contraintes Field → after field_validators
→ before model_validators → construction → after model_validators
```

---

## 5. Le `PATCH` correct — le piège n°1 des API

Trois intentions distinctes du client, que le JSON doit pouvoir exprimer :

| Le client envoie | Intention | Ce que le serveur doit faire |
|---|---|---|
| champ **absent** du body | « n'y touche pas » | garder la valeur actuelle |
| `"description": null` | « efface cette valeur » | mettre `None` |
| `"description": "texte"` | « remplace » | mettre `"texte"` |

### La solution : `model_dump(exclude_unset=True)`

Pydantic mémorise **quels champs ont été explicitement fournis** (les *fields set*).

```python
class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: int | None = None

def apply_patch(current: Task, changes: TaskUpdate) -> Task:
    patch = changes.model_dump(exclude_unset=True)   # SEULS les champs fournis
    return current.model_copy(update=patch)
```

- `PATCH {}` → `patch = {}` → rien ne change.
- `PATCH {"description": null}` → `patch = {"description": None}` → efface.
- `PATCH {"title": "x"}` → `patch = {"title": "x"}` → seul le titre change.

### Le cas ambigu : `exclude_none`

`model_dump(exclude_none=True)` retire **tous** les `None`, y compris les `null` explicites.
Résultat : **impossible d'effacer un champ**. À n'utiliser que si ton API ne permet
volontairement pas l'effacement (documente-le).

### `PUT` vs `PATCH`

- `PUT` = remplacement **complet**. Champ absent = remis à sa valeur par défaut. Body =
  `TaskCreate` (tous les champs).
- `PATCH` = modification **partielle**. Body = `TaskUpdate` (tout optionnel).

La doc FastAPI *Body - Updates* recommande `PATCH` + `exclude_unset` pour les mises à jour
partielles.

---

## 6. Types de données riches (`Extra Data Types`)

Pydantic valide bien plus que `str`/`int` :

| Type | Usage | Entrée acceptée |
|---|---|---|
| `EmailStr` | e-mail (nécessite `email-validator`) | `"a@b.com"` |
| `AnyUrl`, `AnyHttpUrl`, `HttpUrl` | URL | `"https://x.io/p"` |
| `UUID` (`uuid.UUID`) | identifiant | `"a3b…"` (36 car.) |
| `datetime`, `date`, `time`, `timedelta` | temps | ISO 8601 |
| `AwareDatetime`, `NaiveDatetime` | force la présence/absence de fuseau | — |
| `Decimal` | montants (jamais `float` pour de l'argent !) | `"19.99"` |
| `Path` (`pathlib`) | chemin | `"/tmp/x"` |
| `SecretStr` | valeur masquée dans les logs/`repr` | `"hunter2"` |
| `Json` | chaîne JSON à parser | `'{"a":1}'` |
| `bytes`, `Base64Bytes` | binaire | — |

```python
from pydantic import BaseModel, EmailStr, AwareDatetime, Field
from decimal import Decimal

class Invoice(BaseModel):
    customer_email: EmailStr
    amount: Decimal = Field(max_digits=10, decimal_places=2, gt=0)
    issued_at: AwareDatetime
```

> **Argent = `Decimal`.** `0.1 + 0.2 != 0.3` en `float`. Un centime perdu par transaction ×
> un million de transactions = un problème.

---

## 7. Modèles imbriqués & listes de modèles (`Body - Nested Models`)

```python
class ChecklistItem(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    done: bool = False

class TaskCreate(TaskBase):
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=50)

class Point(BaseModel):
    lat: float
    lng: float

class Place(BaseModel):
    name: str
    location: Point                       # objet imbriqué
    aliases: dict[str, str] = {}          # dict typé
```

Pydantic valide **récursivement**. Un `checklist[3].label` vide → 422 avec le chemin exact
(`body.checklist.3.label`). C'est le gros avantage vs valider un `dict` à la main.

Profondeur : garde raisonnable (2–3 niveaux). Au-delà, c'est souvent une sous-ressource qui
mérite son propre endpoint.

---

## 8. Paramètres groupés en modèles

### Query Parameter Models

Quand `GET /tasks` accumule les filtres, regroupe-les :

```python
from typing import Annotated, Literal
from fastapi import Query
from pydantic import BaseModel

class TaskFilters(BaseModel):
    model_config = {"extra": "forbid"}    # ?foo=bar -> 422 (paramètre inconnu rejeté)
    status: TaskStatus | None = None
    min_priority: int | None = Field(default=None, ge=1, le=5)
    q: str | None = Field(default=None, max_length=100)
    sort: Literal["priority", "-priority", "created_at", "-created_at"] = "-priority"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

@app.get("/tasks")
def list_tasks(filters: Annotated[TaskFilters, Query()]) -> TaskPage: ...
```

Avantages : signature courte, filtres testables isolément, réutilisables, `extra: "forbid"`
attrape les fautes de frappe du client.

### Cookie & Header Parameter Models

Même principe pour les cookies et en-têtes (doc *Cookie Parameter Models* / *Header
Parameter Models*) :

```python
class CommonHeaders(BaseModel):
    model_config = {"extra": "forbid"}
    user_agent: str | None = None
    x_request_id: str | None = None

@app.get("/x")
def h(headers: Annotated[CommonHeaders, Header()]): ...
```

---

## 9. `Body - Multiple Parameters` & `Body - Fields`

### Plusieurs corps

```python
@app.put("/tasks/{id}")
def update(id: int, task: TaskUpdate, note: Annotated[str, Body()]): ...
# body attendu : {"task": {...}, "note": "..."}
```

FastAPI « imbrique » automatiquement quand il y a plusieurs modèles + `Body()`.

### Valeur scalaire unique dans le body

```python
@app.post("/tasks/{id}/comment")
def comment(id: int, text: Annotated[str, Body(embed=True, min_length=1)]): ...
# body : {"text": "..."}   (embed=True force l'enveloppe)
```

### `Field` = `Query`/`Path`/`Body` pour l'intérieur d'un modèle

`Field(...)` porte les mêmes contraintes + métadonnées de doc (`description`, `examples`,
`deprecated`) que `Query`/`Path`, mais **à l'intérieur** d'un `BaseModel`.

---

## 10. Exemples de doc (`Declare Request Example Data`)

Trois façons, de la plus locale à la plus globale :

```python
# 1. Sur un champ
title: str = Field(examples=["Rédiger l'ADR"])

# 2. Sur le modèle
class TaskCreate(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [{"title": "Rédiger l'ADR", "priority": 4}]
        }
    }

# 3. Sur le paramètre de la route (plusieurs exemples nommés)
@app.post("/tasks")
def create(
    task: Annotated[TaskCreate, Body(openapi_examples={
        "simple":  {"summary": "Minimal", "value": {"title": "Acheter du café"}},
        "complet": {"summary": "Tous les champs", "value": {"title": "...", "priority": 5, "tags": ["x"]}},
    })],
): ...
```

Une bonne doc a **toujours** des exemples réalistes. Le bouton « Try it out » pré-rempli
divise par 10 le temps de prise en main.

---

## 11. Versionnage des schémas (introduction)

Un contrat public **ne se casse pas** silencieusement. Quand un schéma doit évoluer de façon
incompatible (champ renommé, type changé, champ requis ajouté) :

- **ajout compatible** (nouveau champ optionnel) → pas de version, juste documenter ;
- **changement cassant** → nouveau schéma (`TaskReadV2`) et/ou nouvelle route (`/v2/tasks`) ;
- champ à retirer → le marquer `deprecated=True` dans `Field`, garder N versions, puis retirer.

Le versionnage d'API complet (URI vs header, cycle de dépréciation) est traité au **Module 12**.
Ici, retiens juste : **réfléchis avant de changer un champ que des clients consomment déjà.**

---

## 12. Ce que `taskman` gagne dans ce module

- schémas `TaskCreate` / `TaskUpdate` / `TaskRead` nettement séparés ;
- champ **calculé** `is_overdue` en sortie (jamais en entrée) ;
- sous-ressource imbriquée `checklist: list[ChecklistItem]` ;
- `PATCH` gérant correctement le `null` explicite ;
- `assignee_email: EmailStr | None` ;
- filtres de `GET /tasks` regroupés dans un `TaskFilters` (query model, `extra="forbid"`) ;
- exemples OpenAPI réalistes sur les entrées.

---

## 13. Pièges fréquents

1. **Un seul modèle pour tout** → le client peut fixer `id`, tu fuites `password_hash`.
2. **`exclude_none` au lieu de `exclude_unset`** dans le PATCH → effacement impossible.
3. **`float` pour de l'argent** → erreurs d'arrondi cumulatives.
4. **`datetime` naïf** → `TypeError` à la comparaison, ambiguïté de fuseau. Utilise
   `AwareDatetime`.
5. **Valider un `dict` à la main** au lieu d'un modèle imbriqué → messages d'erreur pauvres,
   pas de doc.
6. **`response_model` qui n'exclut rien** → tu exposes tout l'objet ORM.
7. **Filtres en 8 paramètres** au lieu d'un query model → signature illisible, non testable.
8. **Oublier `email-validator`** → `EmailStr` lève à l'import (`pip install "pydantic[email]"`).
9. **`extra` par défaut = `ignore`** → une faute de frappe du client (`?statuss=done`) passe
   silencieusement. Mets `extra="forbid"` sur les query/header models.
10. **Casser un champ public sans version** → tous les clients existants tombent.

---

## 14. À savoir refaire sans aide après ce module

- Concevoir le trio `Create/Update/Read` pour une entité donnée, avec la bonne hiérarchie.
- Implémenter un `PATCH` qui distingue absent / null / valeur.
- Choisir le bon type riche (`Decimal`, `EmailStr`, `AwareDatetime`, `UUID`).
- Valider une structure imbriquée avec des messages d'erreur précis.
- Regrouper des paramètres en query/header model avec `extra="forbid"`.
- Ajouter des exemples OpenAPI exploitables.

➡️ [Exercices](exercices/README.md) — puis [PAS-A-PAS.md](PAS-A-PAS.md) pour l'explication
ligne par ligne de la solution.
