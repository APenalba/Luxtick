"""Simple in-memory rate limiting middleware."""

import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Per-user rate limiter based on a sliding window of message timestamps."""

    def __init__(self) -> None:
        self._timestamps: dict[int, list[float]] = defaultdict(list)
        self._window_seconds = 60.0
        self._max_requests = settings.rate_limit_per_minute

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.monotonic()
        cutoff = now - self._window_seconds

        # Remove expired timestamps
        self._timestamps[user_id] = [
            ts for ts in self._timestamps[user_id] if ts > cutoff
        ]

        if len(self._timestamps[user_id]) >= self._max_requests:
            logger.warning("Rate limit exceeded for user %d", user_id)
            await event.answer(
                "You're sending messages too fast. Please wait a moment and try again."
            )
            return None

        self._timestamps[user_id].append(now)
        return await handler(event, data)
