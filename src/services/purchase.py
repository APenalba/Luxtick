"""Purchase and receipt business logic."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Receipt, ReceiptItem, Store
from src.db.session import async_session
from src.services.product import ProductMatcher

logger = logging.getLogger(__name__)


def _normalize_store_name(name: str) -> str:
    """Normalize a store name for deduplication."""
    return name.strip().lower().replace("'", "").replace("‘", "").replace("’", "")


def _parse_date(date_str: str | None) -> date:
    """Parse an ISO date string, defaulting to today."""
    if date_str:
        return date.fromisoformat(date_str)
    return date.today()


def _resolve_date_range(
    period: str | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[date | None, date | None]:
    """Convert a period string or explicit dates to a (start, end) date range."""
    if start_date or end_date:
        return (
            date.fromisoformat(start_date) if start_date else None,
            date.fromisoformat(end_date) if end_date else None,
        )

    today = date.today()
    if period == "today":
        return today, today
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "this_month":
        return today.replace(day=1), today
    elif period == "last_month":
        first_of_this_month = today.replace(day=1)
        last_of_prev = first_of_this_month - timedelta(days=1)
        return last_of_prev.replace(day=1), last_of_prev
    elif period == "this_year":
        return today.replace(month=1, day=1), today
    elif period == "last_3_months":
        start = today - timedelta(days=90)
        return start, today
    elif period == "last_year":
        start = today - timedelta(days=365)
        return start, today

    return None, None


class PurchaseService:
    """Service for managing purchases and receipts."""

    def __init__(self) -> None:
        self.product_matcher = ProductMatcher()

    async def search_purchases(
        self,
        user_id: uuid.UUID,
        query: str | None = None,
        store: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search user's purchase history with flexible filters."""
        async with async_session() as session:
            stmt = (
                select(ReceiptItem)
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .join(Store, Receipt.store_id == Store.id, isouter=True)
                .where(Receipt.user_id == user_id)
                .options(
                    selectinload(ReceiptItem.receipt).selectinload(Receipt.store),
                    selectinload(ReceiptItem.product),
                )
                .order_by(Receipt.purchase_date.desc())
                .limit(limit)
            )

            # Apply filters
            if query:
                stmt = stmt.where(ReceiptItem.name_on_receipt.ilike(f"%{query}%"))
            if store:
                stmt = stmt.where(
                    Store.normalized_name.ilike(f"%{_normalize_store_name(store)}%")
                )
            if start_date:
                stmt = stmt.where(
                    Receipt.purchase_date >= date.fromisoformat(start_date)
                )
            if end_date:
                stmt = stmt.where(Receipt.purchase_date <= date.fromisoformat(end_date))

            result = await session.execute(stmt)
            items = list(result.scalars().all())

            return {
                "results": [
                    {
                        "product": item.name_on_receipt,
                        "canonical_name": item.product.canonical_name
                        if item.product
                        else None,
                        "quantity": float(item.quantity),
                        "unit_price": float(item.unit_price),
                        "total_price": float(item.total_price),
                        "store": item.receipt.store.name
                        if item.receipt.store
                        else "Unknown",
                        "date": item.receipt.purchase_date.isoformat(),
                        "discount": float(item.discount_amount)
                        if item.discount_amount
                        else None,
                    }
                    for item in items
                ],
                "count": len(items),
            }

    async def get_product_history(
        self,
        user_id: uuid.UUID,
        product: str,
    ) -> dict[str, Any]:
        """Get full purchase history for a specific product."""
        async with async_session() as session:
            stmt = (
                select(ReceiptItem)
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .where(
                    and_(
                        Receipt.user_id == user_id,
                        ReceiptItem.name_on_receipt.ilike(f"%{product}%"),
                    )
                )
                .options(
                    selectinload(ReceiptItem.receipt).selectinload(Receipt.store),
                )
                .order_by(Receipt.purchase_date.desc())
            )

            result = await session.execute(stmt)
            items = list(result.scalars().all())

            return {
                "product": product,
                "total_purchases": len(items),
                "total_spent": float(sum(i.total_price for i in items)),
                "history": [
                    {
                        "date": item.receipt.purchase_date.isoformat(),
                        "store": item.receipt.store.name
                        if item.receipt.store
                        else "Unknown",
                        "quantity": float(item.quantity),
                        "unit_price": float(item.unit_price),
                        "total_price": float(item.total_price),
                    }
                    for item in items
                ],
            }

    async def add_manual_purchase(
        self,
        user_id: uuid.UUID,
        store_name: str,
        items: list[dict[str, Any]],
        purchase_date: str | None = None,
        total_amount: float | None = None,
    ) -> dict[str, Any]:
        """Add a purchase manually from user input."""
        p_date = _parse_date(purchase_date)

        async with async_session() as session:
            # Find or create store
            store = await self._get_or_create_store(store_name, session)

            # Calculate total from items if not provided
            calculated_total = Decimal("0")
            receipt_items: list[ReceiptItem] = []

            for item_data in items:
                qty = Decimal(str(item_data.get("quantity", 1)))
                unit_price = Decimal(str(item_data["unit_price"]))
                item_total = Decimal(
                    str(item_data.get("total_price", float(qty * unit_price)))
                )
                calculated_total += item_total

                # Match to canonical product
                product, _ = await self.product_matcher.find_or_create_product(
                    item_data["name"], session
                )

                receipt_items.append(
                    ReceiptItem(
                        id=uuid.uuid4(),
                        product_id=product.id,
                        name_on_receipt=item_data["name"],
                        quantity=qty,
                        unit_price=unit_price,
                        total_price=item_total,
                    )
                )

            final_total = (
                Decimal(str(total_amount)) if total_amount else calculated_total
            )

            # Create receipt
            receipt = Receipt(
                id=uuid.uuid4(),
                user_id=user_id,
                store_id=store.id,
                purchase_date=p_date,
                total_amount=final_total,
            )
            session.add(receipt)
            await session.flush()

            # Attach items to receipt
            for item in receipt_items:
                item.receipt_id = receipt.id
                session.add(item)

            await session.commit()

            return {
                "status": "success",
                "receipt_id": str(receipt.id),
                "store": store.name,
                "date": p_date.isoformat(),
                "items_count": len(receipt_items),
                "total": float(final_total),
                "message": f"Purchase of {float(final_total):.2f} EUR at {store.name} on {p_date.isoformat()} saved successfully.",
            }

    async def _get_or_create_store(self, name: str, session: AsyncSession) -> Store:
        """Find an existing store by normalized name or create a new one."""
        normalized = _normalize_store_name(name)
        stmt = select(Store).where(Store.normalized_name == normalized)
        result = await session.execute(stmt)
        store = result.scalar_one_or_none()

        if store is None:
            store = Store(
                id=uuid.uuid4(),
                name=name.strip().title(),
                normalized_name=normalized,
            )
            session.add(store)
            await session.flush()
            logger.info("Created new store: '%s'", store.name)

        return store
