from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. API credentials deliberately stay server-side."""

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.4-mini"

    agentrouter_api_key: str | None = None
    agentrouter_base_url: str = "https://agentrouter.org"
    agentrouter_model: str = "claude-opus-4-8"

    frontend_url: str = "http://localhost:5173"
    demo_mode: bool = True
    # Compatibility for legacy synthetic-data tests only. Keep false in every
    # deployed environment so source corrections cannot bypass Change Control.
    allow_legacy_direct_apply: bool = False
    # Optional reproducibility control; omit it to generate a fresh demo operation on boot.
    demo_seed: int | None = None
    database_url: str = "sqlite:///./nexus.db"
    redis_url: str = "redis://localhost:6379/0"
    uploads_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
