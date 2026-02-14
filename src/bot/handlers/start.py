"""Handlers for /start and /help commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.models import User

router = Router(name="start")

WELCOME_MESSAGE = (
    "Welcome to LuxTick!\n\n"
    "I'm your personal assistant for tracking purchases, receipts, and shopping lists. "
    "Here's what I can do:\n\n"
    "- Ask me anything about your spending (e.g., 'How much did I spend at Mercadona this month?')\n"
    "- Send me a photo of a receipt and I'll extract all the details\n"
    "- Manage shopping lists (e.g., 'Create a shopping list for this week')\n"
    "- Track discounts and offers\n"
    "- Add purchases manually\n\n"
    "Just type your question or send a receipt photo to get started!"
)

HELP_MESSAGE = (
    "Here's what I can help you with:\n\n"
    "**Spending Queries**\n"
    "- 'How much have I spent this month?'\n"
    "- 'How much did I spend on chicken this week?'\n"
    "- 'What do I usually buy weekly?'\n"
    "- 'Compare chicken prices across stores'\n\n"
    "**Receipts**\n"
    "- Send a photo of a receipt to extract items automatically\n"
    "- 'Add a purchase at Mercadona: chicken 5.99, bread 1.20'\n\n"
    "**Shopping Lists**\n"
    "- 'Create a shopping list for the weekend'\n"
    "- 'Add milk and eggs to my list'\n"
    "- 'Show my shopping lists'\n"
    "- 'Suggest what I should buy this week'\n\n"
    "**Discounts**\n"
    "- 'Register: chicken 20% off at Mercadona until Friday'\n"
    "- 'Any discounts at Lidl?'\n\n"
    "Type /help to see this message again."
)


@router.message(Command("start"))
async def cmd_start(message: Message, db_user: User) -> None:
    """Handle the /start command."""
    name = db_user.first_name or db_user.username or "there"
    await message.answer(f"Hi {name}! {WELCOME_MESSAGE}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle the /help command."""
    await message.answer(HELP_MESSAGE, parse_mode="Markdown")
