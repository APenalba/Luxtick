"""Entry point for LuxTick."""

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from src.bot.router import setup_dispatcher
from src.config import settings
from src.db.session import close_engines

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Called when the bot starts up."""
    if settings.is_webhook_mode:
        await bot.set_webhook(
            url=f"{settings.bot_webhook_url}/webhook",
            secret_token=settings.bot_webhook_secret,
        )
        logger.info("Webhook set to %s/webhook", settings.bot_webhook_url)
    else:
        # Ensure any previous webhook is removed before polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared, polling mode ready")
    logger.info("Bot started successfully")


async def on_shutdown(bot: Bot) -> None:
    """Called when the bot shuts down."""
    if settings.is_webhook_mode:
        await bot.delete_webhook()
    await close_engines()
    logger.info("Bot shut down")


async def run_polling() -> None:
    """Run the bot in long-polling mode (development)."""
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = setup_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting bot in polling mode...")
    await dp.start_polling(bot)


def run_webhook() -> None:
    """Run the bot in webhook mode (production)."""
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = setup_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.bot_webhook_secret,
    )
    webhook_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    logger.info("Starting bot in webhook mode on port 8080...")
    web.run_app(app, host="0.0.0.0", port=8080)


def main() -> None:
    """Main entry point: choose polling or webhook mode based on config."""
    if settings.is_webhook_mode:
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
