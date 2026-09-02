"""Schémas Pydantic des tâches (contrats d'entrée / sortie).

Inchangé depuis le Module 02, seulement déplacé de `taskman/models.py` vers
`taskman/schemas/task.py` — les schémas sont une couche à part entière.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

SortKey = Literal["priority", "-priority", "created_at", "-created_at", "due_date", "-due_date"]


class TaskStatus(StrEnum):
    todo = "todo"
    doing = "doing"
    done = "done"


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


class TaskBase(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Titre de la tâche",
        examples=["Rédiger l'ADR sur le découpage en modules"],
    )
    description: str | None = Field(default=None, max_length=5000)
    priority: int = Field(default=3, ge=1, le=5, description="1 = basse … 5 = critique")
    due_date: datetime | None = Field(default=None, description="Échéance (UTC)")
    tags: list[str] = Field(default_factory=list, max_length=10)
    assignee_email: EmailStr | None = Field(default=None, examples=["dev@exemple.org"])
    estimate_hours: Decimal | None = Field(
        default=None, ge=0, max_digits=5, decimal_places=2, examples=["2.50"]
    )
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=50)

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
            t = tag.strip().lower()
            if not (1 <= len(t) <= 20):
                raise ValueError(f"tag invalide : {tag!r} (1 à 20 caractères)")
            cleaned.append(t)
        return cleaned


def _ensure_future(due_date: datetime | None) -> None:
    if due_date is not None:
        now = datetime.now(due_date.tzinfo or UTC)
        if due_date < now:
            raise ValueError("la date d'échéance doit être dans le futur")


class TaskCreate(TaskBase):
    project_id: int = Field(ge=1, description="Projet auquel rattacher la tâche")

    @model_validator(mode="after")
    def _due_date_in_future(self) -> TaskCreate:
        _ensure_future(self.due_date)
        return self


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

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v

    @field_validator("tags")
    @classmethod
    def _tags_shape(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        return [t.strip().lower() for t in tags]

    @model_validator(mode="after")
    def _check_provided_fields(self) -> TaskUpdate:
        provided = self.model_fields_set
        if "title" in provided and self.title is None:
            raise ValueError("title ne peut pas être mis à null")
        if "due_date" in provided:
            _ensure_future(self.due_date)
        return self


class TaskRead(TaskBase):
    model_config = ConfigDict(
        from_attributes=True,  # permet TaskRead.model_validate(orm_row) — Module 04
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "project_id": 1,
                    "title": "Rédiger l'ADR sur le découpage en modules",
                    "description": "3 options, coûts, décision",
                    "priority": 4,
                    "due_date": "2026-12-31T17:00:00Z",
                    "tags": ["docs", "archi"],
                    "assignee_email": "dev@exemple.org",
                    "estimate_hours": "3.00",
                    "checklist": [{"label": "Lister les options", "done": True}],
                    "status": "doing",
                    "created_at": "2026-09-02T09:00:00Z",
                    "updated_at": "2026-09-02T10:30:00Z",
                    "is_overdue": False,
                }
            ]
        },
    )

    id: int
    project_id: int
    status: TaskStatus = TaskStatus.todo
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_overdue(self) -> bool:
        if self.due_date is None or self.status is TaskStatus.done:
            return False
        return self.due_date < datetime.now(self.due_date.tzinfo or UTC)


class TaskPage(BaseModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int


class TaskFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus | None = None
    min_priority: int | None = Field(default=None, ge=1, le=5)
    project_id: int | None = Field(default=None, ge=1)
    q: str | None = Field(default=None, max_length=100, description="Recherche titre + description")
    sort: SortKey = "-priority"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
