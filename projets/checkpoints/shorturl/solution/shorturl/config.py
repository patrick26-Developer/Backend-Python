"""Configuration 12-factor : tout par variable d'environnement, préfixe `SHORTURL_`."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHORTURL_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./shorturl.db"
    db_echo: bool = False
    # base de résolution des liens courts (sert à construire l'URL courte renvoyée)
    base_url: str = "http://localhost:8000"
    alias_length: int = 7
    alias_max_attempts: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
