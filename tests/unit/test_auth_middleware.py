"""Unit tests for the authentication middleware."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.middlewares.auth import AuthMiddleware
from src.db.models import User

pytestmark = pytest.mark.unit


def _make_update(
    tg_id: int = 111,
    username: str = "alice",
    first_name: str = "Alice",
    is_callback: bool = False,
):
    """Create a mock Update with a from_user."""
    from aiogram.types import Update

    update = MagicMock(spec=Update)

    user_mock = MagicMock()
    user_mock.id = tg_id
    user_mock.username = username
    user_mock.first_name = first_name

    if is_callback:
        update.message = None
        update.callback_query = MagicMock()
        update.callback_query.from_user = user_mock
    else:
        update.message = MagicMock()
        update.message.from_user = user_mock
        update.callback_query = None

    return update


def _make_session_mock(existing_user: User | None = None):
    """Create a mock async session that returns the given user (or None)."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_user
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


class TestAuthMiddleware:
    @pytest.fixture
    def middleware(self):
        return AuthMiddleware()

    async def test_new_user_is_created(self, middleware):
        session = _make_session_mock(existing_user=None)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        handler = AsyncMock(return_value="ok")
        update = _make_update(tg_id=999)
        data: dict = {}

        with patch("src.bot.middlewares.auth.async_session", return_value=ctx):
            await middleware(handler, update, data)

        session.add.assert_called_once()
        session.commit.assert_called()
        assert "db_user" in data

    async def test_existing_user_is_found(self, middleware):
        existing = User(
            id=uuid.uuid4(), telegram_id=111, username="alice", first_name="Alice"
        )
        session = _make_session_mock(existing_user=existing)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        handler = AsyncMock(return_value="ok")
        update = _make_update(tg_id=111)
        data: dict = {}

        with patch("src.bot.middlewares.auth.async_session", return_value=ctx):
            await middleware(handler, update, data)

        session.add.assert_not_called()
        assert data["db_user"] is existing

    async def test_username_update_on_change(self, middleware):
        existing = User(
            id=uuid.uuid4(), telegram_id=111, username="old_name", first_name="Alice"
        )
        session = _make_session_mock(existing_user=existing)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        handler = AsyncMock()
        update = _make_update(tg_id=111, username="new_name")
        data: dict = {}

        with patch("src.bot.middlewares.auth.async_session", return_value=ctx):
            await middleware(handler, update, data)

        assert existing.username == "new_name"
        session.commit.assert_called()

    async def test_no_user_in_event_passes_through(self, middleware):
        from aiogram.types import Update

        update = MagicMock(spec=Update)
        update.message = None
        update.callback_query = None

        handler = AsyncMock(return_value="ok")
        data: dict = {}

        _ = await middleware(handler, update, data)
        handler.assert_called_once_with(update, data)
        assert "db_user" not in data

    async def test_handler_receives_db_user(self, middleware):
        existing = User(
            id=uuid.uuid4(), telegram_id=111, username="alice", first_name="Alice"
        )
        session = _make_session_mock(existing_user=existing)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        handler = AsyncMock()
        update = _make_update(tg_id=111)
        data: dict = {}

        with patch("src.bot.middlewares.auth.async_session", return_value=ctx):
            await middleware(handler, update, data)

        handler.assert_called_once()
        _, call_data = handler.call_args.args
        assert "db_user" in call_data

    async def test_callback_query_user_extracted(self, middleware):
        existing = User(
            id=uuid.uuid4(), telegram_id=222, username="bob", first_name="Bob"
        )
        session = _make_session_mock(existing_user=existing)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=False)

        handler = AsyncMock()
        update = _make_update(tg_id=222, is_callback=True)
        data: dict = {}

        with patch("src.bot.middlewares.auth.async_session", return_value=ctx):
            await middleware(handler, update, data)

        assert data["db_user"] is existing
