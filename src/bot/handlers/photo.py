"""Handler for photo messages -- triggers receipt parsing."""

import logging

from aiogram import F, Router
from aiogram.types import Message

from src.agent.receipt_parser import ReceiptParser
from src.db.models import User

logger = logging.getLogger(__name__)

router = Router(name="photo")


@router.message(F.photo)
async def handle_photo(message: Message, db_user: User) -> None:
    """Process a receipt photo: extract data, match products, store in DB."""
    if not message.photo:
        return

    await message.answer("Got your receipt! Let me analyze it...")
    await message.chat.do("typing")

    try:
        # Get the highest resolution photo
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)  # type: ignore[union-attr]

        if not file.file_path:
            await message.answer("Could not download the photo. Please try again.")
            return

        # Download the photo bytes
        from io import BytesIO

        photo_bytes = BytesIO()
        await message.bot.download_file(file.file_path, photo_bytes)  # type: ignore[union-attr]
        photo_bytes.seek(0)

        # Parse the receipt
        parser = ReceiptParser()
        result = await parser.parse_and_store(
            user=db_user,
            image_data=photo_bytes.read(),
        )

        await message.answer(result, parse_mode="Markdown")

    except Exception:
        logger.exception("Error processing receipt from user %d", db_user.telegram_id)
        await message.answer(
            "Sorry, I had trouble reading that receipt. "
            "Please make sure the photo is clear and well-lit, then try again."
        )
