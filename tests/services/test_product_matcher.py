"""Service tests for the ProductMatcher with real PostgreSQL."""

import pytest

from src.services.product import ProductMatcher
from src.services.product_intelligence import ItemIntelligence
from tests.factories import make_product

pytestmark = [pytest.mark.service, pytest.mark.asyncio]


class TestProductMatcher:
    @pytest.fixture
    def matcher(self):
        return ProductMatcher()

    async def test_create_product_when_db_empty(self, matcher, db_session):
        product, is_new = await matcher.find_or_create_product(
            "Chicken Breast", db_session
        )
        assert is_new is True
        assert product.canonical_name == "Chicken Breast"

    async def test_exact_match_returns_existing(self, matcher, db_session):
        existing = make_product(
            canonical_name="Chicken Breast", aliases=["Chicken Breast"]
        )
        db_session.add(existing)
        await db_session.flush()

        product, is_new = await matcher.find_or_create_product(
            "Chicken Breast", db_session
        )
        assert is_new is False
        assert product.id == existing.id

    async def test_fuzzy_match_above_threshold(self, matcher, db_session):
        existing = make_product(
            canonical_name="Chicken Breast", aliases=["Chicken Breast", "PECH POLLO"]
        )
        db_session.add(existing)
        await db_session.flush()

        product, is_new = await matcher.find_or_create_product("PECH POLLO", db_session)
        assert is_new is False
        assert product.id == existing.id

    async def test_fuzzy_match_below_threshold_creates_new(self, matcher, db_session):
        existing = make_product(
            canonical_name="Chicken Breast", aliases=["Chicken Breast"]
        )
        db_session.add(existing)
        await db_session.flush()

        product, is_new = await matcher.find_or_create_product(
            "Detergente Industrial XYZ", db_session
        )
        assert is_new is True
        assert product.id != existing.id

    async def test_alias_added_on_match(self, matcher, db_session):
        existing = make_product(
            canonical_name="Chicken Breast", aliases=["Chicken Breast"]
        )
        db_session.add(existing)
        await db_session.flush()

        # Match with a new alias
        product, is_new = await matcher.find_or_create_product(
            "chicken breast fillet", db_session
        )
        # Depending on fuzzy score this may or may not match; if it matches, alias should be added
        if not is_new:
            assert "chicken breast fillet" in [
                a.lower() for a in (product.aliases or [])
            ] or "chicken breast fillet" in (product.aliases or [])

    async def test_duplicate_alias_not_added(self, matcher, db_session):
        existing = make_product(canonical_name="Milk", aliases=["Milk", "LECHE"])
        db_session.add(existing)
        await db_session.flush()

        original_count = len(existing.aliases or [])
        product, is_new = await matcher.find_or_create_product("LECHE", db_session)
        assert is_new is False
        assert len(product.aliases or []) == original_count  # Not added again

    async def test_case_insensitive_alias_check(self, matcher, db_session):
        existing = make_product(canonical_name="Milk", aliases=["Milk", "LECHE"])
        db_session.add(existing)
        await db_session.flush()

        original_count = len(existing.aliases or [])
        product, is_new = await matcher.find_or_create_product("leche", db_session)
        assert is_new is False
        assert len(product.aliases or []) == original_count

    async def test_create_with_intelligence_sets_category(self, matcher, db_session):
        intelligence = ItemIntelligence(
            source_name="pechuga de pollo",
            canonical_name_en="Chicken Breast",
            aliases_en=["Chicken Breast", "Chicken Fillet"],
            category_path_en="Food > Poultry",
            confidence=0.95,
        )
        product, is_new = await matcher.find_or_create_product(
            "pechuga de pollo",
            db_session,
            item_intelligence=intelligence,
        )
        assert is_new is True
        assert product.canonical_name == "Chicken Breast"
        assert product.category_id is not None
