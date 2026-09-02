"""Modèles ORM (tables). Style SQLAlchemy 2.0 : `Mapped` + `mapped_column`.

Choix de modélisation (Module 04) :
- `tags` et `checklist` sont stockés en colonnes **JSON**. Une checklist avec des
  opérations par item (cocher l'item 3) mériterait sa propre table ; ici on reste
  simple pour se concentrer sur l'async, les sessions et les migrations.
- `status` : enum stocké en texte (`native_enum=False`) — portable SQLite/PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taskman.db.base import Base, TZDateTime, utcnow
from taskman.schemas import TaskStatus


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    tasks: Mapped[list[TaskRow]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project_status", "project_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(5000), default=None)
    priority: Mapped[int] = mapped_column(default=3)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=16), default=TaskStatus.todo, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    assignee_email: Mapped[str | None] = mapped_column(String(320), default=None)
    estimate_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    project: Mapped[ProjectRow] = relationship(back_populates="tasks")
