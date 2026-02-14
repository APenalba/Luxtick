"""Unit tests for the system prompt builder."""

import pytest

from src.agent.prompts import build_system_prompt

pytestmark = pytest.mark.unit


class TestBuildSystemPrompt:
    def test_includes_user_name(self):
        prompt = build_system_prompt(user_name="Alice", user_id="abc-123")
        assert "Alice" in prompt

    def test_includes_currency(self):
        prompt = build_system_prompt(user_name="X", user_id="1", currency="USD")
        assert "USD" in prompt

    def test_includes_date(self):
        prompt = build_system_prompt(
            user_name="X", user_id="1", current_date="2026-02-11"
        )
        assert "2026-02-11" in prompt

    def test_includes_capabilities(self):
        prompt = build_system_prompt(user_name="X", user_id="1")
        assert "spending" in prompt.lower()
        assert "receipt" in prompt.lower()
        assert "shopping" in prompt.lower()

    def test_includes_scope_boundary(self):
        prompt = build_system_prompt(user_name="X", user_id="1")
        assert "ONLY handle" in prompt

    def test_default_values(self):
        prompt = build_system_prompt(user_name="X", user_id="1")
        assert "EUR" in prompt
        assert "UTC" in prompt
