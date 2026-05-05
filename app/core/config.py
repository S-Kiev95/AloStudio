from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- core
    app_env: Literal["local", "test", "staging", "prod"] = "local"
    app_name: str = "alostudio"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(min_length=16)

    # --- db
    database_url: str
    database_url_sync: str

    # --- redis
    redis_url: str
    arq_redis_url: str

    # --- auth
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30

    # --- mail
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "noreply@alostudio.local"

    # --- storage
    storage_backend: Literal["s3", "local"] = "s3"
    s3_endpoint_url: str = "http://localhost:9100"
    s3_region: str = "us-east-1"
    s3_bucket: str = "alostudio"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    # --- parity reference
    chatwoot_ref_base_url: str = "http://localhost:3001"
    chatwoot_ref_api_access_token: str = ""
    chatwoot_ref_admin_email: str = "admin@alostudio.local"
    chatwoot_ref_admin_password: str = "Password123!"

    # --- channels: Facebook Messenger (Phase 5d)
    # Mirrors Rails' ``FB_VERIFY_TOKEN`` env var. Set this to the same
    # value Meta has in the page's webhook subscription so the GET
    # handshake matches. Empty = no Facebook channel will accept the
    # verification (intentional — fail closed).
    fb_verify_token: str = ""
    # Graph API version Meta accepts for ``/me/messages`` calls. Bump
    # in lock-step with what the Chatwoot reference uses so a real
    # Meta-side validation passes against the same schema.
    facebook_api_version: str = "v17.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
