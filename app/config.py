"""
Application configuration management using pydantic-settings.
All values are loaded from environment variables (or a .env file).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── OpenAI ─────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.2

    # ── GitHub ─────────────────────────────────────────────────
    github_token: str = ""
    github_webhook_secret: str = ""

    # ── GitLab ─────────────────────────────────────────────────
    gitlab_token: str = ""
    gitlab_webhook_secret: str = ""
    gitlab_url: str = "https://gitlab.com"

    # ── Bitbucket ──────────────────────────────────────────────
    bitbucket_username: str = ""
    bitbucket_app_password: str = ""
    bitbucket_workspace: str = ""
    bitbucket_webhook_secret: str = ""

    # ── App ────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    max_diff_size_kb: int = 500
    review_cooldown_seconds: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
