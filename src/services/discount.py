"""Discount and offer management service."""

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select

from src.db.models import Category, Discount, Product, Store
from src.db.session import async_session

logger = logging.getLogger(__name__)


class DiscountService:
    """Service for managing and querying discounts/offers."""

    async def get_active_discounts(
        self,
        store: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Get currently active discounts, optionally filtered by store or category."""
        today = date.today()

        async with async_session() as session:
            stmt = (
                select(Discount)
                .join(Store, Discount.store_id == Store.id, isouter=True)
                .join(Product, Discount.product_id == Product.id, isouter=True)
                .join(Category, Discount.category_id == Category.id, isouter=True)
                .where(
                    or_(
                        Discount.end_date >= today,
                        Discount.end_date.is_(None),
                    )
                )
            )

            if store:
                stmt = stmt.where(
                    Store.normalized_name.ilike(f"%{store.strip().lower()}%")
                )
            if category:
                stmt = stmt.where(Category.name.ilike(f"%{category}%"))

            stmt = stmt.order_by(Discount.end_date.asc())

            result = await session.execute(stmt)
            discounts = list(result.scalars().all())

            # Reload relationships
            discount_list = []
            for d in discounts:
                await session.refresh(d, ["store", "product"])
                discount_list.append(
                    {
                        "store": d.store.name if d.store else "Any store",
                        "product": d.product.canonical_name
                        if d.product
                        else "Store-wide",
                        "type": d.discount_type,
                        "value": float(d.value),
                        "description": d.description,
                        "start_date": d.start_date.isoformat()
                        if d.start_date
                        else None,
                        "end_date": d.end_date.isoformat() if d.end_date else None,
                    }
                )

            return {
                "discounts": discount_list,
                "count": len(discount_list),
            }

    async def register_discount(
        self,
        store_name: str,
        discount_type: str,
        value: float,
        product_name: str | None = None,
        description: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Register a new discount or offer."""
        async with async_session() as session:
            # Find or create store
            normalized = store_name.strip().lower().replace("'", "").replace("'", "")
            stmt = select(Store).where(Store.normalized_name == normalized)
            result = await session.execute(stmt)
            store = result.scalar_one_or_none()

            if store is None:
                store = Store(
                    id=uuid.uuid4(),
                    name=store_name.strip().title(),
                    normalized_name=normalized,
                )
                session.add(store)
                await session.flush()

            # Find product if specified
            product_id = None
            if product_name:
                product_stmt = select(Product).where(
                    Product.canonical_name.ilike(f"%{product_name}%")
                )
                result = await session.execute(product_stmt)
                product = result.scalar_one_or_none()
                if product:
                    product_id = product.id

            discount = Discount(
                id=uuid.uuid4(),
                store_id=store.id,
                product_id=product_id,
                discount_type=discount_type,
                value=Decimal(str(value)),
                description=description,
                start_date=date.fromisoformat(start_date)
                if start_date
                else date.today(),
                end_date=date.fromisoformat(end_date) if end_date else None,
            )
            session.add(discount)
            await session.commit()

            # Build description
            target = product_name or "store-wide"
            value_desc = (
                f"{value}%" if discount_type == "percentage" else f"{value} EUR off"
            )

            return {
                "status": "success",
                "discount_id": str(discount.id),
                "message": f"Registered discount: {value_desc} on {target} at {store.name}"
                + (f" until {end_date}" if end_date else ""),
            }
