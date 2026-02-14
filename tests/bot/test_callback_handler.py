"""Tests for inline keyboard callback handlers."""

import pytest

from src.bot.handlers.callback import list_item_check, receipt_confirm, receipt_edit
from tests.conftest import make_mock_callback

pytestmark = [pytest.mark.bot, pytest.mark.asyncio]


class TestCallbackHandler:
    async def test_receipt_confirm(self, sample_user):
        cb = make_mock_callback(data="receipt_confirm:abc12345-6789")
        await receipt_confirm(cb, sample_user)
        cb.answer.assert_called_once()
        assert "confirmed" in cb.answer.call_args.args[0].lower()

    async def test_receipt_edit(self, sample_user):
        cb = make_mock_callback(data="receipt_edit:abc12345-6789")
        await receipt_edit(cb, sample_user)
        cb.answer.assert_called_once()
        cb.message.answer.assert_called_once()
        text = cb.message.answer.call_args.args[0]
        assert "correct" in text.lower()

    async def test_list_check(self, sample_user):
        cb = make_mock_callback(data="list_check:item12345")
        await list_item_check(cb, sample_user)
        cb.answer.assert_called_once()

    async def test_callback_with_none_data(self, sample_user):
        cb = make_mock_callback(data=None)
        # Should not crash
        await receipt_confirm(cb, sample_user)
