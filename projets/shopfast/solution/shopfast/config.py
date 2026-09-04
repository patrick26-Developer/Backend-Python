"""Config 12-factor — préfixe `SHOPFAST_`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-not-secret-change-me-with-openssl-rand-hex-32"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHOPFAST_", env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./shopfast.db"
    db_echo: bool = False

    jwt_secret: SecretStr = SecretStr(_DEV_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # une commande "pending" non payée est abandonnée après ce délai (le stock est rendu)
    order_ttl_minutes: int = 30

    @property
    def is_production(self) -> bool:
        return self.env in {"prod", "production", "staging"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
