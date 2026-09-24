from functools import lru_cache

from pydantic import Field
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
    project_original_image_max_bytes: int = 50 * 1024 * 1024
    project_thumbnail_max_bytes: int = 5 * 1024 * 1024
    project_thumbnail_max_width: int = 512
    project_thumbnail_webp_quality: int = 80
    project_layer_blob_max_bytes: int = 100 * 1024 * 1024
    http_compression_minimum_size: int = 1024
    cors_allow_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="SERVICE_ENGINE_CORS_ALLOW_ORIGINS",
    )
    dev_login_allowlist: str = Field(
        default="",
        validation_alias="SERVICE_ENGINE_DEV_LOGIN_ALLOWLIST",
    )
    invite_codes: str = Field(
        default="",
        validation_alias="SERVICE_ENGINE_INVITE_CODES",
    )

    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    def dev_login_allowed_emails(self) -> set[str]:
        # Empty allowlist = open (unchanged); non-empty = only these emails may dev-login.
        return {e.strip().lower() for e in self.dev_login_allowlist.split(",") if e.strip()}

    def signup_invite_codes(self) -> set[str]:
        return {c.strip() for c in self.invite_codes.split(",") if c.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
