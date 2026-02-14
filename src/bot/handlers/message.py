"""Handler for free-form text messages -- forwards them to the LLM agent."""

import logging

from aiogram import F, Router
from aiogram.types import Message

from src.agent.core import AgentCore
from src.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="message")


@router.message(F.text)
async def handle_text_message(message: Message, db_user: User) -> None:
    """Process a free-form text message through the LLM agent."""
    if not message.text:
        return

    # Show typing indicator while processing
    await message.chat.do("typing")

    try:
        agent = AgentCore()
        response = await agent.process_message(
            user=db_user,
            message_text=message.text,
        )
        await message.answer(response, parse_mode="Markdown")
    except Exception:
        logger.exception("Error processing message from user %d", db_user.telegram_id)
        await message.answer(
            "Sorry, something went wrong while processing your message. Please try again."
        )
