"""Point de départ des exercices du Module 01.

Copie ce fichier :  cp exercices/starter/main.py exercices/main.py
Lance :             fastapi dev 01-fondations-http-et-fastapi/exercices/main.py

Suis les TODO dans l'ordre des exercices (voir exercices/README.md).
Tu peux tout mettre ici pour commencer, puis extraire `models.py` et `store.py`
(exercices 01.3 et 01.4).
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="taskman (exercices module 01)", version="0.1.0")


# ---------------------------------------------------------------------------
# Exercice 01.1 — First steps & OpenAPI
# ---------------------------------------------------------------------------
# TODO 1a : GET "/"        -> {"name": "taskman", "version": "0.1.0", "docs": "/docs"}
# TODO 1b : GET "/health"  -> {"status": "ok"}
#           Annote le type de retour de chaque fonction.


# ---------------------------------------------------------------------------
# Exercice 01.2 — Path & query parameters
# ---------------------------------------------------------------------------
# TODO 2 : GET "/echo/{item_id}"
#   - item_id : int >= 1               (Path)
#   - q       : str | None, max 50     (Query)
#   - verbose : bool = False           (Query)
#   Réponse : {"item_id", "q", "verbose"} ; si verbose -> ajoute "length".


# ---------------------------------------------------------------------------
# Exercice 01.3 — Modèles Pydantic  (à mettre dans models.py)
# ---------------------------------------------------------------------------
# TODO 3 : TaskStatus (Enum), TaskCreate, TaskUpdate, Task.
#   Puis : from .models import ...   (ou import models)


# ---------------------------------------------------------------------------
# Exercice 01.4 — Store en mémoire  (à mettre dans store.py)
# ---------------------------------------------------------------------------
# TODO 4 : InMemoryTaskStore avec create / get / list / update / delete.
#   store = InMemoryTaskStore()


# ---------------------------------------------------------------------------
# Exercice 01.5 — CRUD complet
# ---------------------------------------------------------------------------
# TODO 5a : POST   /tasks           -> 201 + en-tête Location
# TODO 5b : GET    /tasks           -> filtres status / min_priority / limit / offset
# TODO 5c : GET    /tasks/{id}      -> 200 ou 404
# TODO 5d : PATCH  /tasks/{id}      -> 200 ou 404, application partielle
# TODO 5e : DELETE /tasks/{id}      -> 204 ou 404


# ---------------------------------------------------------------------------
# Exercice 01.6 — Finitions
# ---------------------------------------------------------------------------
# TODO 6 : réponse paginée {items,total,limit,offset}, tri `sort`, justifications.
