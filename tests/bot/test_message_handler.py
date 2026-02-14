"""Tests for the free-form text message handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.message import handle_text_message
from tests.conftest import make_mock_message

pytestmark = [pytest.mark.bot, pytest.mark.asyncio]


class TestMessageHandler:
    async def test_text_message_calls_agent(self, sample_user):
        msg = make_mock_message(text="How much did I spend?")
        mock_agent = MagicMock()
        mock_agent.process_message = AsyncMock(return_value="You spent 50 EUR.")

        with patch("src.bot.handlers.message.AgentCore", return_value=mock_agent):
            await handle_text_message(msg, sample_user)

        mock_agent.process_message.assert_called_once()

    async def test_sends_typing_indicator(self, sample_user):
        msg = make_mock_message(text="Hello")
        mock_agent = MagicMock()
        mock_agent.process_message = AsyncMock(return_value="Hi!")

        with patch("src.bot.handlers.message.AgentCore", return_value=mock_agent):
            await handle_text_message(msg, sample_user)

        msg.chat.do.assert_called_with("typing")

    async def test_returns_agent_response(self, sample_user):
        msg = make_mock_message(text="Hello")
        mock_agent = MagicMock()
        mock_agent.process_message = AsyncMock(return_value="Agent says hello!")

        with patch("src.bot.handlers.message.AgentCore", return_value=mock_agent):
            await handle_text_message(msg, sample_user)

        msg.answer.assert_called_once()
        assert "Agent says hello!" in msg.answer.call_args.args[0]

    async def test_agent_error_sends_apology(self, sample_user):
        msg = make_mock_message(text="Hello")
        mock_agent = MagicMock()
        mock_agent.process_message = AsyncMock(side_effect=Exception("Boom"))

        with patch("src.bot.handlers.message.AgentCore", return_value=mock_agent):
            await handle_text_message(msg, sample_user)

        msg.answer.assert_called_once()
        text = msg.answer.call_args.args[0]
        assert "sorry" in text.lower() or "wrong" in text.lower()

    async def test_empty_text_is_skipped(self, sample_user):
        msg = make_mock_message(text=None)

        with patch("src.bot.handlers.message.AgentCore") as mock_agent:
            await handle_text_message(msg, sample_user)

        mock_agent.assert_not_called()
