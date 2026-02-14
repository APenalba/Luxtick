"""Shopping list management service."""

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.db.models import Product, Receipt, ReceiptItem, ShoppingList, ShoppingListItem
from src.db.session import async_session
from src.services.product import ProductMatcher

logger = logging.getLogger(__name__)


class ShoppingListService:
    """Service for creating, updating, and querying shopping lists."""

    def __init__(self) -> None:
        self.product_matcher = ProductMatcher()

    async def create_list(
        self,
        user_id: uuid.UUID,
        name: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a new shopping list with optional initial items."""
        async with async_session() as session:
            shopping_list = ShoppingList(
                id=uuid.uuid4(),
                user_id=user_id,
                name=name,
            )
            session.add(shopping_list)
            await session.flush()

            created_items = []
            for item_data in items:
                item_name = item_data["name"]
                product, _ = await self.product_matcher.find_or_create_product(
                    item_name, session
                )

                list_item = ShoppingListItem(
                    id=uuid.uuid4(),
                    list_id=shopping_list.id,
                    product_id=product.id,
                    custom_name=item_name,
                    quantity=Decimal(str(item_data.get("quantity", 1))),
                    unit=item_data.get("unit"),
                    notes=item_data.get("notes"),
                )
                session.add(list_item)
                created_items.append(item_name)

            await session.commit()

            return {
                "status": "success",
                "list_id": str(shopping_list.id),
                "name": name,
                "items_count": len(created_items),
                "items": created_items,
                "message": f"Shopping list '{name}' created with {len(created_items)} items.",
            }

    async def update_list(
        self,
        user_id: uuid.UUID,
        list_name: str,
        add_items: list[dict[str, Any]] | None = None,
        remove_items: list[str] | None = None,
        check_items: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing shopping list."""
        async with async_session() as session:
            # Find the list
            stmt = (
                select(ShoppingList)
                .where(
                    and_(
                        ShoppingList.user_id == user_id,
                        ShoppingList.name.ilike(f"%{list_name}%"),
                        ShoppingList.is_active == True,  # noqa: E712
                    )
                )
                .options(selectinload(ShoppingList.items))
            )
            result = await session.execute(stmt)
            shopping_list = result.scalar_one_or_none()

            if shopping_list is None:
                return {
                    "status": "error",
                    "message": f"No active shopping list found matching '{list_name}'.",
                }

            changes: list[str] = []

            # Add items
            if add_items:
                for item_data in add_items:
                    item_name = item_data["name"]
                    product, _ = await self.product_matcher.find_or_create_product(
                        item_name, session
                    )
                    list_item = ShoppingListItem(
                        id=uuid.uuid4(),
                        list_id=shopping_list.id,
                        product_id=product.id,
                        custom_name=item_name,
                        quantity=Decimal(str(item_data.get("quantity", 1))),
                        unit=item_data.get("unit"),
                        notes=item_data.get("notes"),
                    )
                    session.add(list_item)
                    changes.append(f"Added: {item_name}")

            # Remove items
            if remove_items:
                for item_name in remove_items:
                    for existing in shopping_list.items:
                        if (
                            existing.custom_name
                            and existing.custom_name.lower() == item_name.lower()
                        ):
                            await session.delete(existing)
                            changes.append(f"Removed: {item_name}")
                            break

            # Check items
            if check_items:
                for item_name in check_items:
                    for existing in shopping_list.items:
                        if (
                            existing.custom_name
                            and existing.custom_name.lower() == item_name.lower()
                        ):
                            existing.is_checked = True
                            changes.append(f"Checked: {item_name}")
                            break

            await session.commit()

            return {
                "status": "success",
                "list_name": shopping_list.name,
                "changes": changes,
                "message": f"Updated '{shopping_list.name}': {', '.join(changes)}.",
            }

    async def get_lists(
        self,
        user_id: uuid.UUID,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """Get the user's shopping lists."""
        async with async_session() as session:
            stmt = (
                select(ShoppingList)
                .where(ShoppingList.user_id == user_id)
                .options(
                    selectinload(ShoppingList.items).selectinload(
                        ShoppingListItem.product
                    )
                )
                .order_by(ShoppingList.created_at.desc())
            )
            if active_only:
                stmt = stmt.where(ShoppingList.is_active == True)  # noqa: E712

            result = await session.execute(stmt)
            lists = list(result.scalars().all())

            return {
                "lists": [
                    {
                        "name": sl.name,
                        "is_active": sl.is_active,
                        "created_at": sl.created_at.isoformat(),
                        "items": [
                            {
                                "name": item.custom_name
                                or (
                                    item.product.canonical_name
                                    if item.product
                                    else "Unknown"
                                ),
                                "quantity": float(item.quantity),
                                "unit": item.unit,
                                "is_checked": item.is_checked,
                                "notes": item.notes,
                            }
                            for item in sl.items
                        ],
                    }
                    for sl in lists
                ],
                "count": len(lists),
            }

    async def suggest_list(
        self,
        user_id: uuid.UUID,
        based_on: str = "weekly_habits",
    ) -> dict[str, Any]:
        """Suggest a shopping list based on purchase patterns."""
        from datetime import date, timedelta

        today = date.today()

        if based_on == "weekly_habits":
            period_days = 30  # Look at last month to find weekly patterns
        elif based_on == "monthly_habits":
            period_days = 90
        else:
            period_days = 30

        d_start = today - timedelta(days=period_days)

        async with async_session() as session:
            # Find most frequently purchased items in the period
            stmt = (
                select(
                    func.coalesce(
                        Product.canonical_name, ReceiptItem.name_on_receipt
                    ).label("product"),
                    func.count(ReceiptItem.id).label("times_bought"),
                    func.avg(ReceiptItem.quantity).label("avg_quantity"),
                    Product.default_unit.label("unit"),
                )
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .join(Product, ReceiptItem.product_id == Product.id, isouter=True)
                .where(
                    and_(
                        Receipt.user_id == user_id,
                        Receipt.purchase_date >= d_start,
                    )
                )
                .group_by(
                    Product.canonical_name,
                    ReceiptItem.name_on_receipt,
                    Product.default_unit,
                )
                .order_by(func.count(ReceiptItem.id).desc())
                .limit(15)
            )
            result = await session.execute(stmt)
            rows = result.all()

            suggestions = [
                {
                    "name": row.product,
                    "suggested_quantity": round(float(row.avg_quantity), 1),
                    "unit": row.unit,
                    "frequency": f"Bought {int(row.times_bought)} times in the last {period_days} days",
                }
                for row in rows
            ]

            return {
                "based_on": based_on,
                "period_analyzed": f"Last {period_days} days",
                "suggestions": suggestions,
                "message": f"Based on your {based_on.replace('_', ' ')}, here are suggested items for your next shopping trip.",
            }
