"""Spending analytics and summary services."""

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select

from src.db.models import Category, Product, Receipt, ReceiptItem, Store
from src.db.session import async_session
from src.services.product import ProductResolver

logger = logging.getLogger(__name__)


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
        return today - timedelta(days=90), today
    elif period == "last_year":
        return today - timedelta(days=365), today
    elif period == "all_time":
        return None, None

    # Default: this month
    return today.replace(day=1), today


class AnalyticsService:
    """Service for spending analytics and summaries."""

    def __init__(self) -> None:
        self.product_resolver = ProductResolver()

    async def get_spending_summary(
        self,
        user_id: uuid.UUID,
        period: str | None = None,
        group_by: str | None = None,
        store: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregated spending statistics."""
        d_start, d_end = _resolve_date_range(period, start_date, end_date)

        async with async_session() as session:
            # Base query: total spending
            base_filters = [Receipt.user_id == user_id]
            if d_start:
                base_filters.append(Receipt.purchase_date >= d_start)
            if d_end:
                base_filters.append(Receipt.purchase_date <= d_end)
            if store:
                base_filters.append(
                    Store.normalized_name.ilike(f"%{store.strip().lower()}%")
                )

            # Total spending
            if category:
                total_stmt = (
                    select(
                        func.sum(ReceiptItem.total_price).label("total"),
                        func.count(func.distinct(Receipt.id)).label("receipt_count"),
                    )
                    .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                    .join(Store, Receipt.store_id == Store.id, isouter=True)
                    .join(Product, ReceiptItem.product_id == Product.id, isouter=True)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .where(and_(*base_filters))
                    .where(Category.name.ilike(f"%{category.strip()}%"))
                )
            else:
                total_stmt = (
                    select(
                        func.sum(Receipt.total_amount).label("total"),
                        func.count(Receipt.id).label("receipt_count"),
                    )
                    .join(Store, Receipt.store_id == Store.id, isouter=True)
                    .where(and_(*base_filters))
                )
            total_result = await session.execute(total_stmt)
            total_row = total_result.one()
            total_amount = float(total_row.total or 0)
            receipt_count = int(total_row.receipt_count or 0)

            # Breakdown by group
            breakdown: list[dict[str, Any]] = []
            if group_by == "store":
                breakdown = await self._group_by_store(session, base_filters)
            elif group_by == "category":
                breakdown = await self._group_by_category(
                    session, base_filters, user_id, d_start, d_end
                )
            elif group_by == "product":
                breakdown = await self._group_by_product(
                    session, user_id, d_start, d_end, store, category
                )
            elif group_by in ("day", "week", "month"):
                breakdown = await self._group_by_time(session, base_filters, group_by)

            period_desc = period or "custom range"
            if d_start and d_end:
                period_desc = f"{d_start.isoformat()} to {d_end.isoformat()}"

            return {
                "period": period_desc,
                "total_spent": total_amount,
                "receipt_count": receipt_count,
                "average_per_receipt": round(total_amount / receipt_count, 2)
                if receipt_count
                else 0,
                "breakdown": breakdown,
            }

    async def _group_by_store(
        self,
        session: Any,
        base_filters: list[Any],
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Store.name,
                func.sum(Receipt.total_amount).label("total"),
                func.count(Receipt.id).label("visits"),
            )
            .join(Store, Receipt.store_id == Store.id, isouter=True)
            .where(and_(*base_filters))
            .group_by(Store.name)
            .order_by(func.sum(Receipt.total_amount).desc())
        )
        result = await session.execute(stmt)
        return [
            {
                "name": row.name or "Unknown",
                "total": float(row.total),
                "visits": int(row.visits),
            }
            for row in result.all()
        ]

    async def _group_by_category(
        self,
        session: Any,
        base_filters: list[Any],
        user_id: uuid.UUID,
        d_start: date | None,
        d_end: date | None,
    ) -> list[dict[str, Any]]:
        filters = [Receipt.user_id == user_id]
        if d_start:
            filters.append(Receipt.purchase_date >= d_start)
        if d_end:
            filters.append(Receipt.purchase_date <= d_end)

        stmt = (
            select(
                func.coalesce(Category.name, "Uncategorized").label("category"),
                func.sum(ReceiptItem.total_price).label("total"),
                func.count(ReceiptItem.id).label("item_count"),
            )
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .join(Product, ReceiptItem.product_id == Product.id, isouter=True)
            .join(Category, Product.category_id == Category.id, isouter=True)
            .where(and_(*filters))
            .group_by(Category.name)
            .order_by(func.sum(ReceiptItem.total_price).desc())
        )
        result = await session.execute(stmt)
        return [
            {
                "name": row.category,
                "total": float(row.total),
                "items": int(row.item_count),
            }
            for row in result.all()
        ]

    async def _group_by_product(
        self,
        session: Any,
        user_id: uuid.UUID,
        d_start: date | None,
        d_end: date | None,
        store: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = [Receipt.user_id == user_id]
        if d_start:
            filters.append(Receipt.purchase_date >= d_start)
        if d_end:
            filters.append(Receipt.purchase_date <= d_end)
        if store:
            filters.append(Store.normalized_name.ilike(f"%{store.strip().lower()}%"))
        if category:
            filters.append(Category.name.ilike(f"%{category.strip()}%"))

        stmt = (
            select(
                func.coalesce(
                    Product.canonical_name, ReceiptItem.name_on_receipt
                ).label("product"),
                func.sum(ReceiptItem.total_price).label("total"),
                func.sum(ReceiptItem.quantity).label("total_qty"),
                func.count(ReceiptItem.id).label("purchase_count"),
            )
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .join(Store, Receipt.store_id == Store.id, isouter=True)
            .join(Product, ReceiptItem.product_id == Product.id, isouter=True)
            .join(Category, Product.category_id == Category.id, isouter=True)
            .where(and_(*filters))
            .group_by(Product.canonical_name, ReceiptItem.name_on_receipt)
            .order_by(func.sum(ReceiptItem.total_price).desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        return [
            {
                "name": row.product,
                "total": float(row.total),
                "quantity": float(row.total_qty),
                "purchases": int(row.purchase_count),
            }
            for row in result.all()
        ]

    async def _group_by_time(
        self,
        session: Any,
        base_filters: list[Any],
        granularity: str,
    ) -> list[dict[str, Any]]:
        time_col: Any
        if granularity == "day":
            time_col = Receipt.purchase_date
        elif granularity == "week":
            time_col = func.date_trunc("week", Receipt.purchase_date)
        else:  # month
            time_col = func.date_trunc("month", Receipt.purchase_date)

        stmt = (
            select(
                time_col.label("period"),
                func.sum(Receipt.total_amount).label("total"),
                func.count(Receipt.id).label("receipt_count"),
            )
            .join(Store, Receipt.store_id == Store.id, isouter=True)
            .where(and_(*base_filters))
            .group_by(time_col)
            .order_by(time_col)
        )
        result = await session.execute(stmt)
        return [
            {
                "period": str(row.period),
                "total": float(row.total),
                "receipts": int(row.receipt_count),
            }
            for row in result.all()
        ]

    async def get_frequent_purchases(
        self,
        user_id: uuid.UUID,
        period: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get the most frequently purchased products."""
        d_start, d_end = _resolve_date_range(period, None, None)

        async with async_session() as session:
            filters = [Receipt.user_id == user_id]
            if d_start:
                filters.append(Receipt.purchase_date >= d_start)
            if d_end:
                filters.append(Receipt.purchase_date <= d_end)

            stmt = (
                select(
                    func.coalesce(
                        Product.canonical_name, ReceiptItem.name_on_receipt
                    ).label("product"),
                    func.count(ReceiptItem.id).label("times_bought"),
                    func.sum(ReceiptItem.quantity).label("total_quantity"),
                    func.sum(ReceiptItem.total_price).label("total_spent"),
                    func.avg(ReceiptItem.unit_price).label("avg_price"),
                )
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .join(Product, ReceiptItem.product_id == Product.id, isouter=True)
                .where(and_(*filters))
                .group_by(Product.canonical_name, ReceiptItem.name_on_receipt)
                .order_by(func.count(ReceiptItem.id).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()

            return {
                "period": period or "all_time",
                "frequent_items": [
                    {
                        "product": row.product,
                        "times_bought": int(row.times_bought),
                        "total_quantity": float(row.total_quantity),
                        "total_spent": float(row.total_spent),
                        "average_price": round(float(row.avg_price), 2),
                    }
                    for row in rows
                ],
            }

    async def compare_prices(
        self,
        user_id: uuid.UUID,
        product: str,
        store: str | None = None,
        period: str | None = None,
    ) -> dict[str, Any]:
        """Compare prices for a product across stores and/or over time."""
        d_start, d_end = _resolve_date_range(period or "last_3_months", None, None)

        async with async_session() as session:
            resolved = await self.product_resolver.resolve_products(product, session)
            if resolved.product_ids:
                product_filter = ReceiptItem.product_id.in_(resolved.product_ids)
            else:
                product_filter = ReceiptItem.name_on_receipt.ilike(f"%{product}%")

            filters = [Receipt.user_id == user_id, product_filter]
            if d_start:
                filters.append(Receipt.purchase_date >= d_start)
            if d_end:
                filters.append(Receipt.purchase_date <= d_end)
            if store:
                filters.append(
                    Store.normalized_name.ilike(f"%{store.strip().lower()}%")
                )

            stmt = (
                select(
                    Store.name.label("store"),
                    func.avg(ReceiptItem.unit_price).label("avg_price"),
                    func.min(ReceiptItem.unit_price).label("min_price"),
                    func.max(ReceiptItem.unit_price).label("max_price"),
                    func.count(ReceiptItem.id).label("purchase_count"),
                )
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .join(Store, Receipt.store_id == Store.id, isouter=True)
                .where(and_(*filters))
                .group_by(Store.name)
                .order_by(func.avg(ReceiptItem.unit_price))
            )
            result = await session.execute(stmt)
            rows = result.all()

            return {
                "product": product,
                "period": period or "last_3_months",
                "comparisons": [
                    {
                        "store": row.store or "Unknown",
                        "average_price": round(float(row.avg_price), 2),
                        "min_price": float(row.min_price),
                        "max_price": float(row.max_price),
                        "purchase_count": int(row.purchase_count),
                    }
                    for row in rows
                ],
            }
