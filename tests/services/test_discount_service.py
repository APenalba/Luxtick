"""Service tests for DiscountService with real PostgreSQL."""

from datetime import date

import pytest

from src.services.discount import DiscountService

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestRegisterDiscount:
    @pytest.fixture
    def service(self):
        return DiscountService()

    async def test_percentage(self, service, patch_db_session):
        result = await service.register_discount(
            store_name="Mercadona",
            discount_type="percentage",
            value=20.0,
        )
        assert result["status"] == "success"
        assert "20" in result["message"]

    async def test_fixed(self, service, patch_db_session):
        result = await service.register_discount(
            store_name="Lidl",
            discount_type="fixed",
            value=1.50,
        )
        assert result["status"] == "success"

    async def test_creates_store_if_new(self, service, patch_db_session):
        result = await service.register_discount(
            store_name="NewStore",
            discount_type="percentage",
            value=10.0,
        )
        assert result["status"] == "success"

    async def test_with_product(self, service, patch_db_session, seed_data):
        result = await service.register_discount(
            store_name="Mercadona",
            discount_type="percentage",
            value=15.0,
            product_name="Chicken",
        )
        assert result["status"] == "success"

    async def test_store_wide(self, service, patch_db_session):
        result = await service.register_discount(
            store_name="Lidl",
            discount_type="percentage",
            value=5.0,
            description="Store-wide sale",
        )
        assert result["status"] == "success"
        assert "store-wide" in result["message"]


class TestGetActiveDiscounts:
    @pytest.fixture
    def service(self):
        return DiscountService()

    async def test_excludes_expired(self, service, patch_db_session, seed_data):
        result = await service.get_active_discounts()
        for d in result["discounts"]:
            if d["end_date"]:
                assert date.fromisoformat(d["end_date"]) >= date.today()

    async def test_includes_no_end_date(self, service, patch_db_session, seed_data):
        result = await service.get_active_discounts()
        has_perpetual = any(d["end_date"] is None for d in result["discounts"])
        assert has_perpetual

    async def test_filter_by_store(self, service, patch_db_session, seed_data):
        result = await service.get_active_discounts(store="Mercadona")
        for d in result["discounts"]:
            assert d["store"] == "Mercadona"

    async def test_empty(self, service, patch_db_session, db_session):
        # No discounts in a clean DB
        result = await service.get_active_discounts()
        assert result["count"] == 0
