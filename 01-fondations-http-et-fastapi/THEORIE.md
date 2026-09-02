# Module 01 — Fondations : HTTP & FastAPI

> **Objectif** : comprendre ce qui se passe *sous* FastAPI (HTTP, ASGI), puis écrire un CRUD
> complet, typé, validé et auto-documenté — sans base de données.
>
> **Durée estimée** : 4 à 8 h (théorie + exercices).
> **Pré-requis** : Module 00 terminé, `venv` actif, `pip install -e ".[dev]"` fait.

---

## 1. HTTP, le minimum vital

Une API REST, c'est un dialogue **requête → réponse** au-dessus de HTTP. Tu dois maîtriser
quatre notions.

### 1.1 Les méthodes (verbes)

| Méthode | Intention | Idempotent ? | Corps de requête ? | Statut succès typique |
|---|---|---|---|---|
| `GET` | Lire une ressource | ✅ | non | 200 |
| `POST` | Créer une ressource / action | ❌ | oui | 201 (créé) ou 200 |
| `PUT` | Remplacer *entièrement* une ressource | ✅ | oui | 200 / 204 |
| `PATCH` | Modifier *partiellement* une ressource | ❌ (en général) | oui | 200 |
| `DELETE` | Supprimer une ressource | ✅ | non | 204 (pas de contenu) |

**Idempotent** = envoyer la requête 1 fois ou 5 fois produit le *même état serveur*.
`DELETE /tasks/42` deux fois → la tâche est supprimée, point (la 2ᵉ fois renvoie 404, mais
l'état est identique). `POST /tasks` deux fois → deux tâches. Cette propriété est cruciale
pour les *retries* réseau (Module 12).

### 1.2 Les codes de statut

Tu dois connaître ceux-ci par cœur :

- **2xx — succès** : `200 OK`, `201 Created`, `204 No Content`.
- **3xx — redirection** : `304 Not Modified` (cache).
- **4xx — le client a tort** : `400 Bad Request`, `401 Unauthorized` (non authentifié),
  `403 Forbidden` (authentifié mais pas le droit), `404 Not Found`,
  `409 Conflict` (état incompatible, ex. doublon), `422 Unprocessable Entity`
  (validation — FastAPI l'utilise automatiquement), `429 Too Many Requests`.
- **5xx — le serveur a tort** : `500 Internal Server Error`, `503 Service Unavailable`.

> Règle : une erreur **prévue** (ressource absente, validation) n'est **jamais** un 500.
> Un 500 = un bug de ton côté que tu dois corriger.

### 1.3 Les en-têtes (headers)

Métadonnées de la requête/réponse : `Content-Type: application/json`,
`Authorization: Bearer <token>`, `Accept`, `Location` (URL de la ressource créée après un
`POST`), `Cache-Control`. On les manipulera vraiment aux Modules 05, 06, 08, 10.

### 1.4 Anatomie d'une ressource REST

Une **ressource** est une entité nommée par une URL. On raisonne en *noms au pluriel*, pas
en verbes :

```
GET    /tasks           -> liste des tâches
POST   /tasks           -> crée une tâche
GET    /tasks/{id}      -> une tâche
PATCH  /tasks/{id}      -> modifie une tâche
DELETE /tasks/{id}      -> supprime une tâche
GET    /projects/{id}/tasks  -> tâches d'un projet (sous-ressource)
```

❌ `GET /getTasks`, `POST /createTask`, `POST /tasks/42/delete` — c'est du RPC déguisé, pas
du REST.

---

## 2. ASGI : pourquoi FastAPI est *async-first*

### WSGI (l'ancien monde : Flask, Django classique)

Un worker traite **une requête à la fois**, du début à la fin. Pendant qu'il attend la base
de données (des millisecondes = une éternité CPU), il **ne fait rien d'autre**. Pour tenir
la charge, on multiplie les process/threads → coûteux en RAM.

### ASGI (FastAPI, Starlette)

Un worker peut avoir **des centaines de requêtes en cours**. Quand l'une attend une I/O
(DB, appel HTTP externe, fichier), le worker **rend la main** (`await`) et traite une autre
requête. C'est l'*event loop*.

```
WSGI  : [req1------attente DB------req1 fin][req2...]      (séquentiel)
ASGI  : [req1 début][req2 début][req1 reprend][req3]...    (entrelacé)
```

**Conséquence pratique que tu dois intégrer dès maintenant** : dans une fonction `async def`,
tu ne dois **jamais** faire d'opération bloquante (I/O synchrone, calcul CPU lourd,
`time.sleep`). Ça gèle *toute* la boucle et donc *toutes* les requêtes. (Détails et parades
au Module 08. FastAPI a un filet de sécurité : une route `def` normale est exécutée dans un
*threadpool*.)

**Uvicorn** est le serveur ASGI qui fait tourner l'*event loop* et parle HTTP. `fastapi dev`
lance Uvicorn avec le rechargement automatique.

---

## 3. Premier contact avec FastAPI

```python
from fastapi import FastAPI

app = FastAPI(title="taskman", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```bash
fastapi dev taskman/main.py
```

- `http://127.0.0.1:8000/health` → `{"status":"ok"}`
- `http://127.0.0.1:8000/docs` → **Swagger UI**, généré automatiquement
- `http://127.0.0.1:8000/redoc` → **ReDoc**, autre rendu de la même doc
- `http://127.0.0.1:8000/openapi.json` → le **contrat OpenAPI** de ton API, en JSON

Ce dernier point est le super-pouvoir de FastAPI : **la doc n'est pas écrite à la main, elle
est dérivée de tes annotations de type**. Si le code et la doc divergent, c'est un bug de
code, pas de doc.

---

## 4. Les trois sources de données d'une requête

FastAPI décide *d'où* vient chaque paramètre de ta fonction selon sa déclaration :

| Source | Où c'est | Déclaration |
|---|---|---|
| **Path** | dans l'URL : `/tasks/{task_id}` | le nom est dans le chemin |
| **Query** | après le `?` : `/tasks?status=done&limit=10` | paramètre simple pas dans le chemin |
| **Body** | corps JSON de la requête | type = modèle Pydantic |

### 4.1 Path parameters

```python
@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> Task:
    ...
```

`task_id: int` → FastAPI **convertit et valide**. `/tasks/abc` renvoie automatiquement une
422. Contraintes plus fines avec `Path` :

```python
from typing import Annotated
from fastapi import Path

@app.get("/tasks/{task_id}")
def get_task(task_id: Annotated[int, Path(ge=1)]) -> Task: ...
```

### 4.2 Query parameters

```python
from typing import Annotated, Literal
from fastapi import Query

@app.get("/tasks")
def list_tasks(
    status: Annotated[Literal["todo", "doing", "done"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Task]:
    ...
```

- **valeur par défaut fournie** (`= None`, `= 20`) → paramètre **optionnel** ;
- **pas de défaut** → paramètre **requis** ; l'absence renvoie 422 ;
- `Literal[...]` restreint les valeurs acceptées et le documente.

### 4.3 Body : les modèles Pydantic

```python
from pydantic import BaseModel, Field

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5)

@app.post("/tasks", status_code=201)
def create_task(payload: TaskCreate) -> Task:
    ...
```

Un paramètre dont le type est un `BaseModel` → FastAPI le lit dans le **corps JSON**, le
valide, et le documente. Corps invalide → 422 détaillée, sans une ligne de code de ta part.

---

## 5. Pydantic v2 — le cœur de FastAPI

Pydantic transforme des classes annotées en **validateurs + (dé)sérialiseurs**.

### 5.1 Modèle de base

```python
from datetime import datetime
from pydantic import BaseModel, Field

class Task(BaseModel):
    id: int
    title: str
    description: str | None = None
    priority: int = 3
    done: bool = False
    created_at: datetime
```

- l'ordre : `nom: type = défaut` ;
- `str | None = None` : optionnel, peut valoir `null` ;
- `str | None` **sans** défaut : requis, mais peut valoir `null` (nuance importante — Module 02).

### 5.2 Contraintes avec `Field`

```python
title: str = Field(min_length=1, max_length=200, description="Titre affiché")
priority: int = Field(default=3, ge=1, le=5)
tags: list[str] = Field(default_factory=list, max_length=10)
```

⚠️ **Piège classique** : pour un défaut *mutable* (liste, dict), utilise
`default_factory=list`, **jamais** `= []` (le `[]` serait partagé entre toutes les
instances — Pydantic v2 te protège en partie mais garde le réflexe).

### 5.3 Validateurs

```python
from pydantic import field_validator, model_validator

class TaskCreate(BaseModel):
    title: str
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v

    @model_validator(mode="after")
    def check_due_date(self) -> "TaskCreate":
        if self.due_date and self.due_date < datetime.now(self.due_date.tzinfo):
            raise ValueError("la date d'échéance doit être dans le futur")
        return self
```

- `field_validator` : valide/normalise **un champ** ;
- `model_validator(mode="after")` : valide **des relations entre champs**, après le parsing.

Un `ValueError` levé dans un validateur → FastAPI renvoie une **422** propre.

### 5.4 Coercition (conversion de types)

Pydantic **convertit** quand c'est sûr : `"3"` (query/path) → `3` pour un `int`.
En mode `strict`, il refuse. Par défaut, sois conscient que `"true"`, `1`, `"1"` peuvent
devenir `True` pour un `bool`.

### 5.5 Sérialisation

```python
task.model_dump()             # -> dict Python
task.model_dump(mode="json")  # -> dict JSON-compatible (datetime -> str ISO)
task.model_dump_json()        # -> str JSON
Task.model_validate(data)     # dict -> instance validée
```

---

## 6. `response_model` / type de retour : le contrat de sortie

L'annotation de retour de ta fonction **est** le modèle de réponse. FastAPI :

1. **filtre** la sortie sur ce modèle (les champs en trop sont retirés — utile pour ne pas
   fuiter un `password_hash`) ;
2. **valide** la sortie (un bug qui renvoie une donnée mal formée est attrapé) ;
3. **documente** la réponse dans `/docs`.

```python
@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> TaskRead:   # <- contrat de sortie
    ...
```

> Dès le Module 02, on aura `TaskCreate` (entrée) ≠ `TaskRead` (sortie). Pour le Module 01,
> on peut se contenter d'un `Task` unique — mais garde en tête que c'est provisoire.

---

## 7. Gérer le « pas trouvé » proprement

```python
from fastapi import HTTPException

@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> Task:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

`HTTPException` est le moyen *rapide* de renvoyer une erreur HTTP. Au Module 05, on
remplacera ça par des exceptions **métier** (`TaskNotFoundError`) traduites en HTTP par un
handler central — pour ne pas éparpiller les `raise HTTPException` dans tout le code.

---

## 8. Async ou pas, pour le Module 01 ?

Sans I/O réelle (tout est en mémoire), `def` suffit et est même plus simple. On écrira
`async def` à partir du Module 04, quand la base de données async l'imposera. **Ne mets pas
`async` par superstition** : `async def` + code bloquant dedans = le pire des deux mondes.

---

## 9. Le store en mémoire (échafaudage du Module 01)

On simule la persistance avec un dictionnaire et un compteur. C'est **jetable** : ça
disparaît au redémarrage, ce n'est pas *thread-safe*, et ça sera remplacé au Module 04. Le
but est d'isoler l'apprentissage de HTTP/FastAPI de celui des bases de données.

```python
class InMemoryTaskStore:
    def __init__(self) -> None:
        self._items: dict[int, Task] = {}
        self._seq: int = 0

    def add(self, data: TaskCreate) -> Task: ...
    def get(self, task_id: int) -> Task | None: ...
    def list(self) -> list[Task]: ...
    def update(self, task_id: int, changes: dict) -> Task | None: ...
    def delete(self, task_id: int) -> bool: ...
```

---

## 10. Pièges fréquents (à relire avant les exercices)

1. **Renvoyer un `dict` non typé** → pas de validation, pas de doc utile. Annote toujours le
   retour.
2. **Confondre 401 et 403** : 401 = « je ne sais pas qui tu es » ; 403 = « je sais, et non ».
3. **`POST` qui renvoie 200 au lieu de 201** à la création.
4. **`DELETE` qui renvoie un corps** : préfère `204 No Content`.
5. **Paramètre requis sans le vouloir** : oublier le `= None` rend le query param obligatoire.
6. **Mettre la logique métier dans la route** : ça passe au Module 01, ça devient une dette
   au Module 03. Garde les routes fines.
7. **`async def` + `time.sleep()` / `requests.get()`** : tu gèles la boucle.
8. **Muter un défaut de liste/dict** partagé entre instances.
9. **Exposer des champs internes** en renvoyant l'objet complet sans `response_model`.
10. **Numéroter les versions d'API trop tard** : on verra `/v1` au Module 12, mais anticipe
    le préfixe.

---

## 11. Ce que tu dois savoir refaire sans aide après ce module

- Expliquer la différence WSGI/ASGI et ses conséquences.
- Choisir la bonne méthode HTTP et le bon code de statut pour une opération donnée.
- Décider si un paramètre est *path*, *query* ou *body*.
- Écrire un modèle Pydantic avec contraintes et validateurs.
- Implémenter un CRUD complet avec 404 propre et statuts corrects.
- Lire l'`openapi.json` généré et y retrouver tes endpoints.

➡️ Passe aux [exercices](exercices/README.md). Fais-les **avant** d'ouvrir `solutions/`.
Ensuite, [`PAS-A-PAS.md`](PAS-A-PAS.md) explique la solution **ligne par ligne**.
