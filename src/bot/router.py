"""Central router setup: registers all handler routers and middlewares."""

from aiogram import Dispatcher

from src.bot.handlers import callback, message, photo, start
from src.bot.middlewares.auth import AuthMiddleware
from src.bot.middlewares.rate_limit import RateLimitMiddleware


def setup_dispatcher() -> Dispatcher:
    """Create and configure the aiogram Dispatcher with all routers and middlewares."""
    dp = Dispatcher()

    # Register middlewares (applied in order)
    dp.update.middleware(AuthMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # Register handler routers (order matters -- commands first, then general handlers)
    dp.include_router(start.router)
    dp.include_router(photo.router)
    dp.include_router(callback.router)
    dp.include_router(message.router)  # Catch-all for free-form text -- must be last

    return dp
