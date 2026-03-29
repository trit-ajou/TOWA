from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TOWA Model Engine"
    app_env: str = "local"
    service_engine_url: str = Field(
        default="http://service-engine:8000",
        validation_alias="TOWA_SERVICE_ENGINE_URL",
    )
    service_engine_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="TOWA_SERVICE_ENGINE_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
