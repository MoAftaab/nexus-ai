from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. API credentials deliberately stay server-side."""

    openai_api_key: str | None = None
    # Policy: NexusAI only calls the requested OpenAI mini model family.
    openai_model: str = "gpt-5.4-mini"
    frontend_url: str = "http://localhost:5173"
    demo_mode: bool = True
    # Optional reproducibility control; omit it to generate a fresh demo operation on boot.
    demo_seed: int | None = None
    database_url: str = "sqlite:///./nexus.db"
    redis_url: str = "redis://localhost:6379/0"
    uploads_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("openai_model")
    @classmethod
    def require_requested_mini_model(cls, value: str) -> str:
        if value != "gpt-5.4-mini":
            raise ValueError("NexusAI is intentionally restricted to the requested OpenAI gpt-5.4-mini model")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
