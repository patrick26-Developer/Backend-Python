"""Tables : `services`, `checks` (résultats de sonde), `incidents`."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from statuspage.db import Base, TZDateTime


class ServiceRow(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(2048))
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())

    checks: Mapped[list[CheckRow]] = relationship(back_populates="service", cascade="all, delete")


class CheckRow(Base):
    __tablename__ = "checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    up: Mapped[bool] = mapped_column(Boolean)
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    latency_ms: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(String(300), default=None)
    checked_at: Mapped[datetime] = mapped_column(TZDateTime, index=True, server_default=func.now())

    service: Mapped[ServiceRow] = relationship(back_populates="checks")


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(
        String(20), default="investigating"
    )  # investigating|resolved
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
