"""Tests for /start and /help command handlers."""

import pytest

from src.bot.handlers.start import cmd_help, cmd_start
from tests.conftest import make_mock_message

pytestmark = [pytest.mark.bot, pytest.mark.asyncio]


class TestStartHandler:
    async def test_start_command_sends_welcome(self, sample_user):
        msg = make_mock_message(text="/start")
        await cmd_start(msg, sample_user)
        msg.answer.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Test" in text  # user's first_name
        assert "Welcome" in text

    async def test_help_command_sends_help(self):
        msg = make_mock_message(text="/help")
        await cmd_help(msg)
        msg.answer.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "Spending" in text or "spending" in text.lower()

    async def test_start_includes_capabilities_list(self, sample_user):
        msg = make_mock_message(text="/start")
        await cmd_start(msg, sample_user)
        text = msg.answer.call_args.args[0]
        assert "receipt" in text.lower()
        assert "shopping" in text.lower()
