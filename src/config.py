"""Application configuration loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_site_url: str = ""
    openrouter_app_name: str = ""

    # Environment runtime
    log_level: str = "INFO"
    openenv_dataset_path: str = "data/pr_tasks.jsonl"
    openenv_max_steps: int = 1

    @field_validator("openai_model")
    @classmethod
    def validate_openai_model(cls, value: str) -> str:
        """Require a non-empty model string for any OpenAI-compatible provider."""
        normalized = (value or "").strip().lower()
        if not normalized:
            raise ValueError("OPENAI_MODEL must not be empty")
        return value

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "env_ignore_empty": True,
    }


settings = Settings()
