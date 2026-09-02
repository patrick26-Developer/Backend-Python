"""Schémas Pydantic de taskman.

Module 01 : séparation entrée (`TaskCreate`) / modification (`TaskUpdate`) /
sortie (`Task`). Voir 01-fondations-http-et-fastapi/solutions/README.md pour le
raisonnement derrière ces choix.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class TaskStatus(StrEnum):
    todo = "todo"
    doing = "doing"
    done = "done"


class TaskBase(BaseModel):
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
    """Corps de `POST /tasks`."""


class TaskUpdate(BaseModel):
    """Corps de `PATCH /tasks/{id}` — tous les champs optionnels."""

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
    id: int
    status: TaskStatus = TaskStatus.todo
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    items: list[Task]
    total: int
    limit: int
    offset: int
