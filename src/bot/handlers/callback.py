"""Handler for inline keyboard callback queries."""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="callback")


@router.callback_query(F.data.startswith("receipt_confirm:"))
async def receipt_confirm(callback: CallbackQuery, db_user: User) -> None:
    """Handle receipt confirmation callback."""
    if callback.data is None:
        return

    receipt_id = callback.data.split(":")[1]
    await callback.answer("Receipt confirmed!")
    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Receipt `{receipt_id[:8]}...` has been saved successfully.",
            parse_mode="Markdown",
        )


@router.callback_query(F.data.startswith("receipt_edit:"))
async def receipt_edit(callback: CallbackQuery, db_user: User) -> None:
    """Handle receipt edit request callback."""
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Please tell me what needs to be corrected. For example:\n"
            "'The total should be 45.30' or 'Remove the second item'."
        )


@router.callback_query(F.data.startswith("list_check:"))
async def list_item_check(callback: CallbackQuery, db_user: User) -> None:
    """Handle checking/unchecking a shopping list item."""
    if callback.data is None:
        return

    item_id = callback.data.split(":")[1]
    await callback.answer("Item toggled!")
    logger.info(
        "Shopping list item %s toggled by user %s", item_id, db_user.telegram_id
    )
