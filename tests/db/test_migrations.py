"""Database migration tests."""

import pytest
from sqlalchemy import inspect

from src.db.models import Base

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

EXPECTED_TABLES = {
    "users",
    "stores",
    "categories",
    "products",
    "receipts",
    "receipt_items",
    "discounts",
    "shopping_lists",
    "shopping_list_items",
}


class TestMigrations:
    async def test_upgrade_creates_all_tables(self, db_engine):
        """All 9 expected tables exist after metadata.create_all."""
        async with db_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )
        assert EXPECTED_TABLES.issubset(table_names), (
            f"Missing tables: {EXPECTED_TABLES - table_names}"
        )

    async def test_downgrade_drops_all_tables(self, db_engine):
        """Dropping all metadata tables removes them."""
        # First drop
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        async with db_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )

        for table in EXPECTED_TABLES:
            assert table not in table_names

        # Re-create for other tests
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def test_upgrade_is_idempotent(self, db_engine):
        """Running create_all twice doesn't error."""
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with db_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )
        assert EXPECTED_TABLES.issubset(table_names)
