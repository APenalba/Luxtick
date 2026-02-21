"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings, loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Telegram --
    telegram_bot_token: str

    # -- LLM API Keys --
    gemini_api_key: str = ""
    openai_api_key: str

    # -- Database --
    database_url: str = "postgresql+asyncpg://localhost:5433/luxtick"
    database_url_readonly: str = "postgresql+asyncpg://localhost:5433/luxtick"

    # -- Bot --
    bot_webhook_url: str = ""
    bot_webhook_secret: str = ""

    # -- Models --
    conversational_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o"
    item_intelligence_model: str = "gpt-4o-mini"

    # -- Feature Flags --
    enable_item_intelligence: bool = True

    # -- Rate Limiting --
    rate_limit_per_minute: int = 20

    # -- Logging --
    log_level: str = "INFO"

    @property
    def is_webhook_mode(self) -> bool:
        """Return True if the bot should run in webhook mode."""
        return bool(self.bot_webhook_url)


settings = Settings()
