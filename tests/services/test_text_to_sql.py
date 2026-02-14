"""Service tests for TextToSQLService with real PostgreSQL."""

import uuid

import pytest

from src.services.text_to_sql import TextToSQLService

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestTextToSQL:
    @pytest.fixture
    def service(self):
        return TextToSQLService()

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    async def test_execute_valid_select(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="How many stores?",
            sql_query="SELECT COUNT(*) as cnt FROM stores",
        )
        assert result["status"] == "success"
        assert result["row_count"] >= 1

    async def test_auto_adds_limit(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="All stores",
            sql_query="SELECT * FROM stores",
        )
        assert result["status"] == "success"
        assert "LIMIT" in result["sql_executed"]

    async def test_preserves_existing_limit(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Top 2 stores",
            sql_query="SELECT * FROM stores LIMIT 2",
        )
        assert result["status"] == "success"
        assert result["row_count"] <= 2

    async def test_rejects_insert(self, service, user_id, patch_readonly_session):
        result = await service.execute_query(
            user_id=user_id,
            question="Bad query",
            sql_query="INSERT INTO stores (name) VALUES ('evil')",
        )
        assert result["status"] == "error"

    async def test_rejects_drop(self, service, user_id, patch_readonly_session):
        result = await service.execute_query(
            user_id=user_id,
            question="Bad query",
            sql_query="DROP TABLE stores",
        )
        assert result["status"] == "error"

    async def test_rejects_empty_query(self, service, user_id, patch_readonly_session):
        result = await service.execute_query(
            user_id=user_id,
            question="Empty",
            sql_query="",
        )
        assert result["status"] == "error"

    async def test_returns_columns_and_rows(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Store names",
            sql_query="SELECT name, normalized_name FROM stores",
        )
        assert result["status"] == "success"
        assert "name" in result["columns"]
        assert "normalized_name" in result["columns"]
        assert len(result["rows"]) > 0

    async def test_serializes_uuid(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Store IDs",
            sql_query="SELECT id FROM stores LIMIT 1",
        )
        assert result["status"] == "success"
        if result["rows"]:
            assert isinstance(result["rows"][0]["id"], str)

    async def test_serializes_decimal(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Receipt totals",
            sql_query="SELECT total_amount FROM receipts LIMIT 1",
        )
        assert result["status"] == "success"
        if result["rows"]:
            val = result["rows"][0]["total_amount"]
            assert isinstance(val, (str, int, float))

    async def test_serializes_date(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Purchase dates",
            sql_query="SELECT purchase_date FROM receipts LIMIT 1",
        )
        assert result["status"] == "success"
        if result["rows"]:
            assert isinstance(result["rows"][0]["purchase_date"], str)

    async def test_handles_query_error_gracefully(
        self, service, user_id, patch_readonly_session, seed_data
    ):
        result = await service.execute_query(
            user_id=user_id,
            question="Bad SQL",
            sql_query="SELECT * FROM nonexistent_table_xyz",
        )
        assert result["status"] == "error"
        assert "error" in result
