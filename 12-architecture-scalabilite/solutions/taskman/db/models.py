"""Modèles ORM (tables). Style SQLAlchemy 2.0 : `Mapped` + `mapped_column`.

Module 06 : `UserRow`, `RefreshTokenRow`, et une colonne `owner_id` sur les
projets et les tâches (isolation des données par utilisateur).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from taskman.db.base import Base, TZDateTime, utcnow
from taskman.schemas import TaskStatus, UserRole


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, length=16), default=UserRole.member
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class RefreshTokenRow(Base):
    """Un refresh token émis. `revoked=True` après rotation ou déconnexion."""

    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revoked: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class OutboxRow(Base):
    """*Outbox pattern* (Module 12) : les événements de domaine sont écrits ICI,
    dans la **même transaction** que la donnée. Un worker les publie ensuite sur
    le broker et pose `published_at`."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None, index=True)


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    tasks: Mapped[list[TaskRow]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_owner_status", "owner_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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

    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    project: Mapped[ProjectRow] = relationship(back_populates="tasks")
