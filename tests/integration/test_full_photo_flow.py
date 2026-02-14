"""Integration test: full receipt photo flow from upload to DB storage."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select

from src.agent.receipt_parser import ReceiptParser
from src.db.models import Receipt, ReceiptItem

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

RECEIPT_JSON = {
    "store_name": "Aldi",
    "purchase_date": "2026-02-10",
    "items": [
        {"name": "Apples", "quantity": 1.5, "unit_price": 2.49, "total_price": 3.74},
        {"name": "Pasta", "quantity": 2, "unit_price": 1.15, "total_price": 2.30},
        {"name": "Olive Oil", "quantity": 1, "unit_price": 6.50, "total_price": 6.50},
    ],
    "total": 12.54,
    "currency": "EUR",
    "confidence_notes": [],
}


class TestFullPhotoFlow:
    async def test_receipt_photo_to_database(
        self, patch_db_session, db_session, db_user
    ):
        """Full flow: user sends photo -> vision model extracts JSON -> products matched ->
        receipt + items stored in real DB -> summary returned."""

        # Mock the vision model response
        msg = MagicMock()
        msg.content = json.dumps(RECEIPT_JSON)
        choice = MagicMock()
        choice.message = msg
        vision_resp = MagicMock()
        vision_resp.choices = [choice]

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=vision_resp)

            parser = ReceiptParser()
            summary = await parser.parse_and_store(
                user=db_user, image_data=b"fake-photo"
            )

        # Verify summary contains expected info
        assert "Aldi" in summary
        assert "12.54" in summary
        assert "Apples" in summary
        assert "Pasta" in summary
        assert "Olive Oil" in summary

        # Verify DB state: receipt exists
        stmt = (
            select(func.count())
            .select_from(Receipt)
            .where(Receipt.user_id == db_user.id)
        )
        result = await db_session.execute(stmt)
        receipt_count = result.scalar()
        assert receipt_count >= 1

        # Verify DB state: 3 receipt items exist
        stmt = (
            select(func.count())
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(Receipt.user_id == db_user.id)
        )
        result = await db_session.execute(stmt)
        item_count = result.scalar()
        assert item_count >= 3
