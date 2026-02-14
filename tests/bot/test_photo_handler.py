"""Tests for the receipt photo handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.photo import handle_photo
from tests.conftest import make_mock_message

pytestmark = [pytest.mark.bot, pytest.mark.asyncio]


def _make_photo_message():
    """Create a message with a photo attachment."""
    msg = make_mock_message(text=None)

    photo = MagicMock()
    photo.file_id = "photo_file_123"
    msg.photo = [MagicMock(), photo]  # Two sizes, last is largest

    file = MagicMock()
    file.file_path = "photos/receipt.jpg"
    msg.bot.get_file = AsyncMock(return_value=file)

    async def fake_download(path, dest):
        dest.write(b"fake-image-bytes")

    msg.bot.download_file = AsyncMock(side_effect=fake_download)

    return msg


class TestPhotoHandler:
    async def test_triggers_receipt_parser(self, sample_user):
        msg = _make_photo_message()
        mock_parser = MagicMock()
        mock_parser.parse_and_store = AsyncMock(return_value="Receipt parsed!")

        with patch("src.bot.handlers.photo.ReceiptParser", return_value=mock_parser):
            await handle_photo(msg, sample_user)

        mock_parser.parse_and_store.assert_called_once()

    async def test_sends_analyzing_message(self, sample_user):
        msg = _make_photo_message()
        mock_parser = MagicMock()
        mock_parser.parse_and_store = AsyncMock(return_value="Done!")

        with patch("src.bot.handlers.photo.ReceiptParser", return_value=mock_parser):
            await handle_photo(msg, sample_user)

        # First call to answer should be the "analyzing" message
        first_answer = msg.answer.call_args_list[0]
        assert (
            "analyze" in first_answer.args[0].lower()
            or "receipt" in first_answer.args[0].lower()
        )

    async def test_downloads_highest_resolution(self, sample_user):
        msg = _make_photo_message()
        mock_parser = MagicMock()
        mock_parser.parse_and_store = AsyncMock(return_value="Done!")

        with patch("src.bot.handlers.photo.ReceiptParser", return_value=mock_parser):
            await handle_photo(msg, sample_user)

        # Should use the last photo (highest res)
        msg.bot.get_file.assert_called_once_with("photo_file_123")

    async def test_parser_error_sends_retry_message(self, sample_user):
        msg = _make_photo_message()
        mock_parser = MagicMock()
        mock_parser.parse_and_store = AsyncMock(
            side_effect=Exception("Vision API failed")
        )

        with patch("src.bot.handlers.photo.ReceiptParser", return_value=mock_parser):
            await handle_photo(msg, sample_user)

        last_answer = msg.answer.call_args_list[-1]
        assert (
            "trouble" in last_answer.args[0].lower()
            or "sorry" in last_answer.args[0].lower()
        )

    async def test_no_file_path_sends_error(self, sample_user):
        msg = _make_photo_message()
        file = MagicMock()
        file.file_path = None
        msg.bot.get_file = AsyncMock(return_value=file)

        with patch("src.bot.handlers.photo.ReceiptParser"):
            await handle_photo(msg, sample_user)

        last_answer = msg.answer.call_args_list[-1]
        assert (
            "download" in last_answer.args[0].lower()
            or "could not" in last_answer.args[0].lower()
        )
