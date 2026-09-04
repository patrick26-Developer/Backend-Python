"""Modèle ORM : une ligne `links`. Ne traverse jamais la couche repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shorturl.db import Base, TZDateTime


class LinkRow(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alias: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    target_url: Mapped[str] = mapped_column(String(2048))
    clicks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, server_default=func.now())
    last_clicked_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime, default=None)
