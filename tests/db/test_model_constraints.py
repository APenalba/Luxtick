"""Tests for database model constraints and cascading behavior."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models import (
    Product,
    Receipt,
    ReceiptItem,
    ShoppingListItem,
    User,
)
from tests.factories import (
    make_category,
    make_product,
    make_receipt,
    make_receipt_item,
    make_shopping_list,
    make_shopping_list_item,
    make_store,
    make_user,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


class TestModelConstraints:
    async def test_user_telegram_id_unique(self, db_session):
        u1 = make_user(telegram_id=123456789)
        u2 = make_user(telegram_id=123456789)
        db_session.add(u1)
        await db_session.flush()
        db_session.add(u2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_store_normalized_name_unique(self, db_session):
        s1 = make_store(name="Mercadona", normalized_name="mercadona")
        s2 = make_store(name="MERCADONA", normalized_name="mercadona")
        db_session.add(s1)
        await db_session.flush()
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_receipt_requires_user_id(self, db_session):
        receipt = Receipt(
            id=uuid.uuid4(),
            user_id=None,  # type: ignore
            store_id=None,
            total_amount=10.0,
        )
        db_session.add(receipt)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_receipt_item_cascade_delete(self, db_session):
        user = make_user()
        store = make_store()
        db_session.add_all([user, store])
        await db_session.flush()

        receipt = make_receipt(user_id=user.id, store_id=store.id)
        db_session.add(receipt)
        await db_session.flush()

        item = make_receipt_item(receipt_id=receipt.id)
        db_session.add(item)
        await db_session.flush()

        # Delete receipt -> items should cascade
        await db_session.delete(receipt)
        await db_session.flush()

        stmt = select(ReceiptItem).where(ReceiptItem.id == item.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_shopping_list_item_cascade_delete(self, db_session):
        user = make_user(telegram_id=99999)
        db_session.add(user)
        await db_session.flush()

        lst = make_shopping_list(user_id=user.id)
        db_session.add(lst)
        await db_session.flush()

        item = make_shopping_list_item(list_id=lst.id)
        db_session.add(item)
        await db_session.flush()

        await db_session.delete(lst)
        await db_session.flush()

        stmt = select(ShoppingListItem).where(ShoppingListItem.id == item.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_category_self_reference(self, db_session):
        parent = make_category(name="Meat")
        db_session.add(parent)
        await db_session.flush()

        child = make_category(name="Poultry", parent_id=parent.id)
        db_session.add(child)
        await db_session.flush()

        assert child.parent_id == parent.id

    async def test_product_aliases_array(self, db_session):
        product = make_product(
            canonical_name="Chicken Breast",
            aliases=["Chicken Breast", "PECH POLLO", "Pollo"],
        )
        db_session.add(product)
        await db_session.flush()

        stmt = select(Product).where(Product.id == product.id)
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert loaded.aliases == ["Chicken Breast", "PECH POLLO", "Pollo"]

    async def test_user_preferences_jsonb(self, db_session):
        user = make_user(telegram_id=888888)
        user.preferences = {"currency": "USD", "theme": "dark"}
        db_session.add(user)
        await db_session.flush()

        stmt = select(User).where(User.id == user.id)
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert loaded.preferences == {"currency": "USD", "theme": "dark"}
