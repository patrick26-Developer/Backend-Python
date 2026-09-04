"""Config 12-factor — tout par variable d'environnement, préfixe `STATUSPAGE_`."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STATUSPAGE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./statuspage.db"
    db_echo: bool = False

    log_json: bool = True
    log_level: str = "INFO"

    # worker de sonde
    worker_enabled: bool = True
    worker_tick_seconds: float = 1.0  # fréquence à laquelle le worker cherche des checks dus
    probe_timeout_seconds: float = 5.0
    # /ready renvoie 503 si le worker n'a pas tourné depuis ce délai (≈ 2 intervalles)
    ready_max_worker_staleness_seconds: float = 30.0

    # un service est « dégradé » si sa dernière sonde a échoué ; « en panne » si les 3 dernières.
    outage_consecutive_failures: int = 3
    uptime_window_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
