from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TOWA Service Engine"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://towa:towa@db:5432/towa"
    database_echo: bool = False
    auth_session_ttl_hours: int = 24
    billing_hold_ttl_minutes: int = 30
    initial_credit_units: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()

