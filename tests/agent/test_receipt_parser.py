"""Tests for the receipt parsing pipeline with mocked vision model."""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.receipt_parser import ExtractedReceipt, ReceiptParser

pytestmark = pytest.mark.agent

SAMPLE_RECEIPT_JSON = {
    "store_name": "Mercadona",
    "store_address": "Calle Mayor 1",
    "purchase_date": "2026-02-11",
    "items": [
        {
            "name": "Chicken Breast",
            "quantity": 1,
            "unit_price": 5.99,
            "total_price": 5.99,
        },
        {"name": "Bread", "quantity": 2, "unit_price": 1.20, "total_price": 2.40},
        {"name": "Milk", "quantity": 1, "unit_price": 1.10, "total_price": 1.10},
    ],
    "subtotal": 9.49,
    "tax": 0.00,
    "total": 9.49,
    "currency": "EUR",
    "confidence_notes": [],
}


def _mock_vision_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
class TestExtractFromImage:
    async def test_valid_json(self):
        parser = ReceiptParser()
        resp = _mock_vision_response(json.dumps(SAMPLE_RECEIPT_JSON))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            result = await parser.extract_from_image(b"fake-image-data")

        assert isinstance(result, ExtractedReceipt)
        assert result.store_name == "Mercadona"
        assert len(result.items) == 3
        assert result.total == 9.49

    async def test_with_markdown_fences(self):
        parser = ReceiptParser()
        wrapped = f"```json\n{json.dumps(SAMPLE_RECEIPT_JSON)}\n```"
        resp = _mock_vision_response(wrapped)

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            result = await parser.extract_from_image(b"fake-image-data")

        assert result.store_name == "Mercadona"

    async def test_invalid_json(self):
        parser = ReceiptParser()
        resp = _mock_vision_response("This is not JSON at all")

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            with pytest.raises(ValueError):
                await parser.extract_from_image(b"fake-image-data")

    async def test_missing_required_field(self):
        parser = ReceiptParser()
        bad_data = {"store_name": "X", "items": []}  # missing 'total'
        resp = _mock_vision_response(json.dumps(bad_data))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            with pytest.raises(ValueError):
                await parser.extract_from_image(b"fake-image-data")


@pytest.mark.asyncio
class TestParseAndStore:
    async def test_saves_receipt(self, patch_db_session, db_session, db_user):
        parser = ReceiptParser()
        resp = _mock_vision_response(json.dumps(SAMPLE_RECEIPT_JSON))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            summary = await parser.parse_and_store(user=db_user, image_data=b"fake")

        assert "Mercadona" in summary
        assert "9.49" in summary

    async def test_saves_all_items(self, patch_db_session, db_session, db_user):
        parser = ReceiptParser()
        resp = _mock_vision_response(json.dumps(SAMPLE_RECEIPT_JSON))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            summary = await parser.parse_and_store(user=db_user, image_data=b"fake")

        assert "Chicken Breast" in summary
        assert "Bread" in summary
        assert "Milk" in summary

    async def test_creates_store(self, patch_db_session, db_session, db_user):
        from sqlalchemy import select

        from src.db.models import Store

        parser = ReceiptParser()
        resp = _mock_vision_response(json.dumps(SAMPLE_RECEIPT_JSON))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            await parser.parse_and_store(user=db_user, image_data=b"fake")

        stmt = select(Store).where(Store.normalized_name == "mercadona")
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is not None


class TestBuildSummary:
    def test_format(self):
        parser = ReceiptParser()
        summary = parser._build_summary(
            store_name="Mercadona",
            purchase_date=date(2026, 2, 11),
            items=[
                {
                    "name": "Chicken",
                    "canonical": "Chicken Breast",
                    "is_new": False,
                    "qty": 1,
                    "price": 5.99,
                },
                {
                    "name": "Bread",
                    "canonical": "Bread",
                    "is_new": True,
                    "qty": 2,
                    "price": 2.40,
                },
            ],
            total=8.39,
            currency="EUR",
            confidence_notes=[],
            receipt_id="abc12345-6789",
        )
        assert "Mercadona" in summary
        assert "2026-02-11" in summary
        assert "8.39" in summary
        assert "new product" in summary  # Bread is new

    def test_with_confidence_notes(self):
        parser = ReceiptParser()
        summary = parser._build_summary(
            store_name="X",
            purchase_date=date.today(),
            items=[],
            total=0,
            currency="EUR",
            confidence_notes=["Could not read item 3"],
            receipt_id="abc",
        )
        assert "Could not read item 3" in summary


@pytest.mark.asyncio
class TestImageEncoding:
    async def test_image_sent_as_base64(self):
        """Verify the litellm call includes the image as base64 data URL."""
        import base64

        parser = ReceiptParser()
        image_data = b"fake-image-bytes"
        expected_b64 = base64.b64encode(image_data).decode("utf-8")

        captured_kwargs = {}

        async def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return _mock_vision_response(json.dumps(SAMPLE_RECEIPT_JSON))

        with (
            patch("src.agent.receipt_parser.litellm") as mock_litellm,
            patch("src.agent.receipt_parser.settings") as mock_settings,
        ):
            mock_settings.vision_model = "gpt-4o"
            mock_litellm.acompletion = AsyncMock(side_effect=capture)

            await parser.extract_from_image(image_data)

        messages = captured_kwargs.get("messages", [])
        content = messages[0]["content"]
        image_part = next(p for p in content if p.get("type") == "image_url")
        assert expected_b64 in image_part["image_url"]["url"]
