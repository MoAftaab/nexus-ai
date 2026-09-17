from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. API credentials deliberately stay server-side."""

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.4-mini"

    # CodeCraft exposes an OpenAI-compatible endpoint. Keep its credential
    # separate from OPENAI_API_KEY so deployments can choose the gateway
    # without changing the request contract used by the agent mesh.
    codecraft_api_key: str | None = None
    codecraft_base_url: str = "https://codecraftapi.com/v1"
    codecraft_model: str = "gpt-5.6-luna"

    # Ollama is an optional local fallback. The OpenAI-compatible /v1 route
    # keeps streaming and chat payloads identical to the cloud providers.
    # Opt in when an Ollama daemon is available; disabled by default so a
    # workstation without Ollama stays responsive in deterministic evidence mode.
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1:8b"

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
    # Hackathon: fixed reference date for all overdue/expiry/stale calculations.
    # Corresponds to the dataset snapshot date in the provided workbook README.
    snapshot_date: str = "2026-09-05"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
