"""Unit tests for Pydantic receipt extraction schemas."""

import pytest
from pydantic import ValidationError

from src.agent.receipt_parser import ExtractedItem, ExtractedReceipt

pytestmark = pytest.mark.unit


class TestExtractedItem:
    def test_valid(self):
        item = ExtractedItem(name="Chicken", unit_price=5.99, total_price=5.99)
        assert item.name == "Chicken"
        assert item.unit_price == 5.99

    def test_defaults(self):
        item = ExtractedItem(name="Milk", unit_price=1.10, total_price=1.10)
        assert item.quantity == 1.0
        assert item.discount_amount is None
        assert item.discount_type is None

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            ExtractedItem(unit_price=1.0, total_price=1.0)  # missing name
        with pytest.raises(ValidationError):
            ExtractedItem(name="X", total_price=1.0)  # missing unit_price


class TestExtractedReceipt:
    def test_valid(self):
        receipt = ExtractedReceipt(
            store_name="Mercadona",
            items=[ExtractedItem(name="Bread", unit_price=1.20, total_price=1.20)],
            total=1.20,
        )
        assert receipt.store_name == "Mercadona"
        assert len(receipt.items) == 1

    def test_minimal(self):
        receipt = ExtractedReceipt(
            store_name="Lidl",
            items=[],
            total=0,
        )
        assert receipt.store_name == "Lidl"
        assert receipt.purchase_date is None
        assert receipt.subtotal is None

    def test_empty_items_is_valid(self):
        receipt = ExtractedReceipt(store_name="X", items=[], total=0)
        assert receipt.items == []
