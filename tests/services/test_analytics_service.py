"""Service tests for AnalyticsService with real PostgreSQL."""

import pytest

from src.services.analytics import AnalyticsService

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestSpendingSummary:
    @pytest.fixture
    def service(self):
        return AnalyticsService()

    async def test_this_month(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="this_month"
        )
        assert "total_spent" in result
        assert "receipt_count" in result
        assert isinstance(result["total_spent"], float)

    async def test_by_store(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", group_by="store"
        )
        assert len(result["breakdown"]) > 0
        for entry in result["breakdown"]:
            assert "name" in entry
            assert "total" in entry

    async def test_by_category(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", group_by="category"
        )
        assert len(result["breakdown"]) > 0

    async def test_by_product(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", group_by="product"
        )
        assert len(result["breakdown"]) > 0

    async def test_by_day(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", group_by="day"
        )
        assert len(result["breakdown"]) > 0

    async def test_by_month(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", group_by="month"
        )
        assert len(result["breakdown"]) > 0

    async def test_filtered_by_store(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id, period="last_3_months", store="Mercadona"
        )
        assert result["total_spent"] > 0

    async def test_custom_date_range(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id,
            start_date="2025-01-01",
            end_date="2027-12-31",
        )
        assert result["total_spent"] > 0

    async def test_no_data_returns_zero(self, service, patch_db_session, seed_data):
        result = await service.get_spending_summary(
            user_id=seed_data["user"].id,
            start_date="2020-01-01",
            end_date="2020-01-31",
        )
        assert result["total_spent"] == 0
        assert result["receipt_count"] == 0


class TestFrequentPurchases:
    @pytest.fixture
    def service(self):
        return AnalyticsService()

    async def test_returns_top_items(self, service, patch_db_session, seed_data):
        result = await service.get_frequent_purchases(
            user_id=seed_data["user"].id, period="last_3_months"
        )
        assert len(result["frequent_items"]) > 0
        # Should be sorted by times_bought descending
        counts = [item["times_bought"] for item in result["frequent_items"]]
        assert counts == sorted(counts, reverse=True)

    async def test_respects_limit(self, service, patch_db_session, seed_data):
        result = await service.get_frequent_purchases(
            user_id=seed_data["user"].id, period="last_3_months", limit=3
        )
        assert len(result["frequent_items"]) <= 3

    async def test_last_month(self, service, patch_db_session, seed_data):
        result = await service.get_frequent_purchases(
            user_id=seed_data["user"].id, period="last_month"
        )
        assert "frequent_items" in result


class TestComparePrices:
    @pytest.fixture
    def service(self):
        return AnalyticsService()

    async def test_across_stores(self, service, patch_db_session, seed_data):
        result = await service.compare_prices(
            user_id=seed_data["user"].id, product="Chicken"
        )
        assert len(result["comparisons"]) > 0
        for entry in result["comparisons"]:
            assert "store" in entry
            assert "average_price" in entry

    async def test_single_store(self, service, patch_db_session, seed_data):
        result = await service.compare_prices(
            user_id=seed_data["user"].id, product="Chicken", store="Mercadona"
        )
        for entry in result["comparisons"]:
            assert entry["store"] == "Mercadona"

    async def test_multilingual_alias(self, service, patch_db_session, seed_data):
        result = await service.compare_prices(
            user_id=seed_data["user"].id, product="pollo"
        )
        assert len(result["comparisons"]) > 0

    async def test_no_data(self, service, patch_db_session, seed_data):
        result = await service.compare_prices(
            user_id=seed_data["user"].id, product="Nonexistent XYZ"
        )
        assert result["comparisons"] == []
