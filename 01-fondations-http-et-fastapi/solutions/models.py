"""Solution Module 01 — modèles Pydantic.

Choix de conception (détaillés dans README.md) :
- 3 schémas distincts dès maintenant (TaskCreate / TaskUpdate / Task) : séparer
  entrée et sortie est un principe, pas une optimisation tardive ;
- datetimes toujours *timezone-aware* (UTC) — un datetime naïf est un bug qui
  attend son fuseau ;
- défauts mutables via `default_factory`, jamais `= []`.

NB : on écrit les `Field(...)` directement dans les modèles (et non dans des
variables réutilisées) : un `FieldInfo` partagé entre modèles est fragile.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskStatus(StrEnum):
    """`StrEnum` : chaque membre EST une `str` (`TaskStatus.done == "done"`),

    donc directement sérialisable en JSON et exposé comme enum dans OpenAPI.
    """

    todo = "todo"
    doing = "doing"
    done = "done"


class TaskBase(BaseModel):
    """Champs communs à la création et à la lecture, avec leurs validateurs."""

    title: str = Field(min_length=1, max_length=200, description="Titre de la tâche")
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5, description="1 = basse … 5 = critique")
    due_date: datetime | None = Field(default=None, description="Échéance (UTC)")
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v

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

    @model_validator(mode="after")
    def _due_date_in_future(self) -> TaskBase:
        if self.due_date is not None:
            now = datetime.now(self.due_date.tzinfo or UTC)
            if self.due_date < now:
                raise ValueError("la date d'échéance doit être dans le futur")
        return self


class TaskCreate(TaskBase):
    """Corps de `POST /tasks`. Aucun champ 'serveur' (id, dates, status) accepté."""


class TaskUpdate(BaseModel):
    """Corps de `PATCH /tasks/{id}` : tout est optionnel.

    Version simple pour le Module 01 — le traitement fin du PATCH partiel
    (null explicite vs absent) est le sujet du Module 02.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_date: datetime | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v


class Task(TaskBase):
    """La ressource complète, telle que renvoyée par l'API."""

    id: int
    status: TaskStatus = TaskStatus.todo
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "title": "Rédiger la doc d'architecture",
                    "description": "ADR + schéma des couches",
                    "priority": 4,
                    "due_date": "2026-12-31T17:00:00Z",
                    "tags": ["docs", "archi"],
                    "status": "doing",
                    "created_at": "2026-09-02T09:00:00Z",
                    "updated_at": "2026-09-02T10:30:00Z",
                }
            ]
        }
    }


class TaskPage(BaseModel):
    """Réponse paginée (exercice 01.6)."""

    items: list[Task]
    total: int
    limit: int
    offset: int
