"""Unit tests for the rate limiting middleware."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, Message

from src.bot.middlewares.rate_limit import RateLimitMiddleware

pytestmark = pytest.mark.unit


def _make_message(user_id: int = 111) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    return msg


class TestRateLimitMiddleware:
    @pytest.fixture
    def middleware(self):
        with patch("src.bot.middlewares.rate_limit.settings") as mock_settings:
            mock_settings.rate_limit_per_minute = 3
            mw = RateLimitMiddleware()
        return mw

    async def test_under_limit_passes(self, middleware):
        handler = AsyncMock(return_value="ok")
        msg = _make_message()
        _ = await middleware(handler, msg, {})
        handler.assert_called_once()

    async def test_at_limit_blocks(self, middleware):
        handler = AsyncMock(return_value="ok")
        msg = _make_message(user_id=200)

        # Send 3 messages (at limit)
        for _ in range(3):
            await middleware(handler, msg, {})

        # 4th message should be blocked
        handler.reset_mock()
        _ = await middleware(handler, msg, {})
        handler.assert_not_called()
        msg.answer.assert_called()  # Rate limit message sent

    async def test_window_expires_resets(self, middleware):
        handler = AsyncMock(return_value="ok")
        msg = _make_message(user_id=300)

        # Fill the window
        for _ in range(3):
            await middleware(handler, msg, {})

        # Simulate time passing (clear the internal timestamps)
        middleware._timestamps[300] = [time.monotonic() - 120]  # 2 minutes ago

        handler.reset_mock()
        _ = await middleware(handler, msg, {})
        handler.assert_called_once()  # Passes again

    async def test_different_users_independent(self, middleware):
        handler = AsyncMock(return_value="ok")
        msg_a = _make_message(user_id=400)
        msg_b = _make_message(user_id=401)

        # User A hits limit
        for _ in range(3):
            await middleware(handler, msg_a, {})

        # User B should still pass
        handler.reset_mock()
        _ = await middleware(handler, msg_b, {})
        handler.assert_called_once()

    async def test_non_message_events_pass(self, middleware):
        handler = AsyncMock(return_value="ok")
        cb = MagicMock(spec=CallbackQuery)
        _ = await middleware(handler, cb, {})
        handler.assert_called_once()
