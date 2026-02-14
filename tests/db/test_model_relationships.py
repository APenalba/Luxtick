"""Tests for ORM relationship loading."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models import (
    Category,
    Product,
    Receipt,
    ReceiptItem,
    ShoppingList,
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


class TestModelRelationships:
    async def test_user_has_receipts(self, db_session):
        user = make_user()
        store = make_store()
        db_session.add_all([user, store])
        await db_session.flush()

        r1 = make_receipt(user_id=user.id, store_id=store.id)
        r2 = make_receipt(user_id=user.id, store_id=store.id)
        db_session.add_all([r1, r2])
        await db_session.flush()

        stmt = (
            select(User).where(User.id == user.id).options(selectinload(User.receipts))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert len(loaded.receipts) == 2

    async def test_receipt_has_items(self, db_session):
        user = make_user()
        store = make_store()
        db_session.add_all([user, store])
        await db_session.flush()

        receipt = make_receipt(user_id=user.id, store_id=store.id)
        db_session.add(receipt)
        await db_session.flush()

        i1 = make_receipt_item(receipt_id=receipt.id, name_on_receipt="Item A")
        i2 = make_receipt_item(receipt_id=receipt.id, name_on_receipt="Item B")
        db_session.add_all([i1, i2])
        await db_session.flush()

        stmt = (
            select(Receipt)
            .where(Receipt.id == receipt.id)
            .options(selectinload(Receipt.items))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert len(loaded.items) == 2

    async def test_receipt_item_has_product(self, db_session):
        user = make_user()
        store = make_store()
        product = make_product(canonical_name="Test Product")
        db_session.add_all([user, store, product])
        await db_session.flush()

        receipt = make_receipt(user_id=user.id, store_id=store.id)
        db_session.add(receipt)
        await db_session.flush()

        item = make_receipt_item(receipt_id=receipt.id, product_id=product.id)
        db_session.add(item)
        await db_session.flush()

        stmt = (
            select(ReceiptItem)
            .where(ReceiptItem.id == item.id)
            .options(selectinload(ReceiptItem.product))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert loaded.product is not None
        assert loaded.product.canonical_name == "Test Product"

    async def test_product_has_category(self, db_session):
        cat = make_category(name="Dairy")
        db_session.add(cat)
        await db_session.flush()

        product = make_product(canonical_name="Milk", category_id=cat.id)
        db_session.add(product)
        await db_session.flush()

        stmt = (
            select(Product)
            .where(Product.id == product.id)
            .options(selectinload(Product.category))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert loaded.category is not None
        assert loaded.category.name == "Dairy"

    async def test_category_has_children(self, db_session):
        parent = make_category(name="Meat")
        db_session.add(parent)
        await db_session.flush()

        child1 = make_category(name="Poultry", parent_id=parent.id)
        child2 = make_category(name="Beef", parent_id=parent.id)
        db_session.add_all([child1, child2])
        await db_session.flush()

        stmt = (
            select(Category)
            .where(Category.id == parent.id)
            .options(selectinload(Category.children))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert len(loaded.children) == 2
        child_names = {c.name for c in loaded.children}
        assert child_names == {"Poultry", "Beef"}

    async def test_shopping_list_has_items(self, db_session):
        user = make_user(telegram_id=777777)
        db_session.add(user)
        await db_session.flush()

        lst = make_shopping_list(user_id=user.id)
        db_session.add(lst)
        await db_session.flush()

        i1 = make_shopping_list_item(list_id=lst.id, custom_name="Milk")
        i2 = make_shopping_list_item(list_id=lst.id, custom_name="Bread")
        i3 = make_shopping_list_item(list_id=lst.id, custom_name="Eggs")
        db_session.add_all([i1, i2, i3])
        await db_session.flush()

        stmt = (
            select(ShoppingList)
            .where(ShoppingList.id == lst.id)
            .options(selectinload(ShoppingList.items))
        )
        result = await db_session.execute(stmt)
        loaded = result.scalar_one()
        assert len(loaded.items) == 3
