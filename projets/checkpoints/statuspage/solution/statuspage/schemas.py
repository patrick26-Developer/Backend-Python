"""Contrats d'API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: AnyHttpUrl
    interval_seconds: int = Field(default=60, ge=5, le=3600)
    expected_status: int = Field(default=200, ge=100, le=599)


class ServiceStatus(StrEnum):
    operational = "operational"
    degraded = "degraded"
    outage = "outage"
    unknown = "unknown"


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_seconds: int
    expected_status: int
    current_status: ServiceStatus
    uptime_ratio: float | None  # None si aucune sonde sur la fenêtre
    last_checked_at: datetime | None


class CheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    up: bool
    status_code: int | None
    latency_ms: float
    error: str | None
    checked_at: datetime


class CheckPage(BaseModel):
    items: list[CheckRead]
    total: int
    limit: int
    offset: int


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=4000)


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=4000)
    status: Literal["investigating", "resolved"] | None = None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class StatusSummary(BaseModel):
    overall: ServiceStatus
    services: list[ServiceRead]
    active_incidents: list[IncidentRead]
    generated_at: datetime


SinceParam = Annotated[datetime | None, Field(description="ISO 8601 avec fuseau")]
