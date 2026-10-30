"""Application configuration, sourced from the environment with the ``CREDIT_`` prefix."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import SettingsConfigDict
from zarreh_agentkit.settings import AgentSettings


class Settings(AgentSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CREDIT_", extra="ignore")

    langsmith_project: str = "credit-decisioning"

    db_path: str = "data/credit.db"
    analyst_db_path: str = "data/analyst.db"
    model_path: str = "artifacts/model.joblib"
    evidence_path: str = "artifacts/evidence.json"
    queue_path: str = "data/queue.json"

    # The analyst is the only LLM user. Model choice lives here, never inline.
    analyst_model: str = "gpt-4o-mini"
    analyst_max_model_calls: int = 8
    analyst_max_tool_calls: int = 12
    analyst_max_tool_rounds: int = 3
    analyst_max_message_chars: int = 2000

    write_rate_limit_per_minute: int = 20
    analyst_rate_limit_per_minute: int = 10
    read_rate_limit_per_minute: int = 240
    frontend_origins: list[str] = ["http://localhost:3000"]

    @property
    def analyst_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
