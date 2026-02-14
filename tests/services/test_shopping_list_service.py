"""Service tests for ShoppingListService with real PostgreSQL."""

import pytest

from src.services.shopping_list import ShoppingListService

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestCreateList:
    @pytest.fixture
    def service(self):
        return ShoppingListService()

    async def test_empty_list(self, service, patch_db_session, db_session):
        from tests.factories import make_user

        user = make_user()
        db_session.add(user)
        await db_session.flush()

        result = await service.create_list(user_id=user.id, name="Empty List", items=[])
        assert result["status"] == "success"
        assert result["items_count"] == 0

    async def test_with_items(self, service, patch_db_session, db_session):
        from tests.factories import make_user

        user = make_user()
        db_session.add(user)
        await db_session.flush()

        result = await service.create_list(
            user_id=user.id,
            name="Weekend",
            items=[
                {"name": "Milk", "quantity": 2, "unit": "liters"},
                {"name": "Bread"},
                {"name": "Eggs", "quantity": 12, "unit": "pcs"},
            ],
        )
        assert result["status"] == "success"
        assert result["items_count"] == 3


class TestGetLists:
    @pytest.fixture
    def service(self):
        return ShoppingListService()

    async def test_active_only(self, service, patch_db_session, seed_data):
        result = await service.get_lists(user_id=seed_data["user"].id, active_only=True)
        assert result["count"] >= 1
        for lst in result["lists"]:
            assert lst["is_active"] is True

    async def test_includes_archived(self, service, patch_db_session, seed_data):
        result = await service.get_lists(
            user_id=seed_data["user"].id, active_only=False
        )
        names = [lst["name"] for lst in result["lists"]]
        assert "Old List" in names


class TestUpdateList:
    @pytest.fixture
    def service(self):
        return ShoppingListService()

    async def test_add_items(self, service, patch_db_session, seed_data):
        result = await service.update_list(
            user_id=seed_data["user"].id,
            list_name="Weekly Groceries",
            add_items=[{"name": "Yogurt"}, {"name": "Rice"}],
        )
        assert result["status"] == "success"
        assert any("Added" in c for c in result["changes"])

    async def test_remove_items(self, service, patch_db_session, seed_data):
        result = await service.update_list(
            user_id=seed_data["user"].id,
            list_name="Weekly Groceries",
            remove_items=["Milk"],
        )
        assert result["status"] == "success"
        assert any("Removed" in c for c in result["changes"])

    async def test_check_items(self, service, patch_db_session, seed_data):
        result = await service.update_list(
            user_id=seed_data["user"].id,
            list_name="Weekly Groceries",
            check_items=["Bread"],
        )
        assert result["status"] == "success"
        assert any("Checked" in c for c in result["changes"])

    async def test_not_found(self, service, patch_db_session, seed_data):
        result = await service.update_list(
            user_id=seed_data["user"].id,
            list_name="Nonexistent List",
        )
        assert result["status"] == "error"


class TestSuggestList:
    @pytest.fixture
    def service(self):
        return ShoppingListService()

    async def test_weekly_habits(self, service, patch_db_session, seed_data):
        result = await service.suggest_list(
            user_id=seed_data["user"].id, based_on="weekly_habits"
        )
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

    async def test_empty_history(self, service, patch_db_session, db_session):
        from tests.factories import make_user

        user = make_user(telegram_id=999999)
        db_session.add(user)
        await db_session.flush()

        result = await service.suggest_list(user_id=user.id, based_on="weekly_habits")
        assert result["suggestions"] == []
