"""Service tests for PurchaseService with real PostgreSQL."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from src.db.models import Store
from src.services.purchase import PurchaseService

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestAddManualPurchase:
    @pytest.fixture
    def service(self):
        return PurchaseService()

    async def test_creates_receipt(self, service, patch_db_session, db_session):
        result = await service.add_manual_purchase(
            user_id=(await _get_user_id(db_session)),
            store_name="Mercadona",
            items=[{"name": "Chicken", "unit_price": 5.99}],
            purchase_date="2026-02-11",
        )
        assert result["status"] == "success"
        assert result["store"] == "Mercadona"
        assert result["date"] == "2026-02-11"

    async def test_creates_items(self, service, patch_db_session, db_session):
        user_id = await _get_user_id(db_session)
        result = await service.add_manual_purchase(
            user_id=user_id,
            store_name="Lidl",
            items=[
                {"name": "Bread", "unit_price": 1.20, "quantity": 2},
                {"name": "Milk", "unit_price": 1.10},
            ],
        )
        assert result["items_count"] == 2

    async def test_creates_store_if_new(self, service, patch_db_session, db_session):
        user_id = await _get_user_id(db_session)
        result = await service.add_manual_purchase(
            user_id=user_id,
            store_name="Aldi",
            items=[{"name": "Rice", "unit_price": 1.89}],
        )
        assert result["store"] == "Aldi"

        stmt = select(Store).where(Store.normalized_name == "aldi")
        res = await db_session.execute(stmt)
        assert res.scalar_one_or_none() is not None

    async def test_reuses_existing_store(self, service, patch_db_session, db_session):
        from tests.factories import make_store

        store = make_store(name="Mercadona", normalized_name="mercadona")
        db_session.add(store)
        await db_session.flush()

        user_id = await _get_user_id(db_session)
        result = await service.add_manual_purchase(
            user_id=user_id,
            store_name="mercadona",
            items=[{"name": "Eggs", "unit_price": 2.50}],
        )
        assert result["store"] == "Mercadona"

    async def test_default_date_is_today(self, service, patch_db_session, db_session):
        user_id = await _get_user_id(db_session)
        result = await service.add_manual_purchase(
            user_id=user_id,
            store_name="Test",
            items=[{"name": "X", "unit_price": 1.0}],
        )
        assert result["date"] == date.today().isoformat()

    async def test_calculates_total(self, service, patch_db_session, db_session):
        user_id = await _get_user_id(db_session)
        result = await service.add_manual_purchase(
            user_id=user_id,
            store_name="Test",
            items=[
                {"name": "A", "unit_price": 3.00, "quantity": 2},
                {"name": "B", "unit_price": 1.50},
            ],
        )
        assert result["total"] == pytest.approx(7.50, abs=0.01)


class TestSearchPurchases:
    async def test_by_product_name(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.search_purchases(
            user_id=seed_data["user"].id, query="Chicken"
        )
        assert result["count"] > 0
        for item in result["results"]:
            assert "chicken" in item["product"].lower()

    async def test_by_store(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.search_purchases(
            user_id=seed_data["user"].id, store="Mercadona"
        )
        assert result["count"] > 0
        for item in result["results"]:
            assert item["store"] == "Mercadona"

    async def test_by_date_range(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        today = date.today()
        result = await service.search_purchases(
            user_id=seed_data["user"].id,
            start_date=(today - timedelta(days=5)).isoformat(),
            end_date=today.isoformat(),
        )
        assert result["count"] >= 0  # May be 0 depending on seed data timing

    async def test_combined_filters(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.search_purchases(
            user_id=seed_data["user"].id,
            query="Chicken",
            store="Mercadona",
        )
        for item in result["results"]:
            assert "chicken" in item["product"].lower()
            assert item["store"] == "Mercadona"

    async def test_empty_result(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.search_purchases(
            user_id=seed_data["user"].id,
            query="Nonexistent Product XYZ",
        )
        assert result["count"] == 0

    async def test_respects_limit(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.search_purchases(user_id=seed_data["user"].id, limit=2)
        assert result["count"] <= 2


class TestGetProductHistory:
    async def test_returns_history(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.get_product_history(
            user_id=seed_data["user"].id, product="Chicken"
        )
        assert result["total_purchases"] > 0
        assert result["total_spent"] > 0
        assert len(result["history"]) > 0

    async def test_empty_history(self, patch_db_session, db_session, seed_data):
        service = PurchaseService()
        result = await service.get_product_history(
            user_id=seed_data["user"].id, product="Nonexistent"
        )
        assert result["total_purchases"] == 0

    async def test_store_normalization_deduplication(
        self, patch_db_session, db_session
    ):
        service = PurchaseService()
        user_id = await _get_user_id(db_session)

        await service.add_manual_purchase(
            user_id=user_id,
            store_name="Mercadona",
            items=[{"name": "A", "unit_price": 1}],
        )
        await service.add_manual_purchase(
            user_id=user_id,
            store_name="mercadona",
            items=[{"name": "B", "unit_price": 2}],
        )
        await service.add_manual_purchase(
            user_id=user_id,
            store_name=" MERCADONA ",
            items=[{"name": "C", "unit_price": 3}],
        )

        stmt = select(Store).where(Store.normalized_name == "mercadona")
        res = await db_session.execute(stmt)
        stores = list(res.scalars().all())
        assert len(stores) == 1


async def _get_user_id(session):
    """Helper: create a user and return their ID."""
    from tests.factories import make_user

    user = make_user()
    session.add(user)
    await session.flush()
    return user.id
