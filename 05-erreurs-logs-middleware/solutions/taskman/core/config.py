"""Configuration de l'application, typée et validée.

Règle : **aucun** `os.environ` ailleurs dans le code. Toute la config passe par
`Settings`, chargée une seule fois via `get_settings()`.

Priorité des sources (pydantic-settings) : arguments > variables d'environnement >
fichier `.env` > valeurs par défaut ci-dessous.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",  # APP_ENV, APP_NAME, APP_LOG_LEVEL...
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = "local"
    name: str = "taskman"
    version: str = "0.5.0"

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # JSON en staging/prod ; texte lisible en local (surchargable via APP_LOG_JSON).
    log_json: bool | None = None

    # Module 04 : base de données. Dev par défaut = SQLite local (fichier).
    # Prod = "postgresql+asyncpg://user:pass@host:5432/taskman"
    database_url: str = "sqlite+aiosqlite:///./taskman.db"
    db_echo: bool = False  # True = journalise le SQL (traque des N+1)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def use_json_logs(self) -> bool:
        return self.log_json if self.log_json is not None else self.env != "local"

    @property
    def docs_url(self) -> str | None:
        # Les docs interactives restent ouvertes partout SAUF en production.
        return None if self.is_production else "/docs"


@lru_cache
def get_settings() -> Settings:
    """Instance unique (mémoïsée). En test, on la surcharge via
    `app.dependency_overrides` — voir tests/conftest.py."""
    return Settings()
