"""Authentication middleware: ensures every Telegram user is registered in the database."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy import select

from src.db.models import User
from src.db.session import async_session

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware that auto-registers Telegram users and injects the DB user into handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract the Telegram user from the update
        tg_user = None
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                tg_user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                tg_user = event.callback_query.from_user

        if tg_user is None:
            return await handler(event, data)

        # Look up or create the user in the database
        async with async_session() as session:
            stmt = select(User).where(User.telegram_id == tg_user.id)
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()

            if db_user is None:
                db_user = User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                )
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)
                logger.info(
                    "New user registered: %s (tg_id=%d)", tg_user.username, tg_user.id
                )
            else:
                # Update username/first_name if changed
                changed = False
                if db_user.username != tg_user.username:
                    db_user.username = tg_user.username
                    changed = True
                if db_user.first_name != tg_user.first_name:
                    db_user.first_name = tg_user.first_name
                    changed = True
                if changed:
                    await session.commit()

            data["db_user"] = db_user

        return await handler(event, data)
