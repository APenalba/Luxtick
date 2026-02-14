"""Unit tests for application configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit


class TestConfig:
    def test_is_webhook_mode_true(self):
        from src.config import Settings

        s = Settings(
            telegram_bot_token="x",
            gemini_api_key="x",
            openai_api_key="x",
            bot_webhook_url="https://example.com",
        )
        assert s.is_webhook_mode is True

    def test_is_webhook_mode_false(self):
        from src.config import Settings

        s = Settings(
            telegram_bot_token="x",
            gemini_api_key="x",
            openai_api_key="x",
            bot_webhook_url="",
        )
        assert s.is_webhook_mode is False

    def test_default_values(self):
        from src.config import Settings

        s = Settings(
            telegram_bot_token="x",
            gemini_api_key="x",
            openai_api_key="x",
        )
        assert s.conversational_model == "gpt-4o-mini"
        assert s.vision_model == "gpt-4o"
        assert s.rate_limit_per_minute == 20
        assert s.log_level == "INFO"

    def test_missing_required_raises(self):
        from src.config import Settings

        with pytest.raises(ValidationError):
            # Clear the env and disable .env file so the required field is truly missing
            env = os.environ.copy()
            env.pop("TELEGRAM_BOT_TOKEN", None)
            with patch.dict(os.environ, env, clear=True):
                Settings(gemini_api_key="x", openai_api_key="x", _env_file=None)
