"""Backfill script for product aliases/categories and missing product links.

Usage:
  python -m scripts.reprocess_products --dry-run
  python -m scripts.reprocess_products --batch-size 200
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models import Product, ReceiptItem
from src.db.session import async_session
from src.services.product import ProductMatcher
from src.services.product_intelligence import ProductIntelligenceService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def _reprocess(dry_run: bool, batch_size: int) -> None:
    matcher = ProductMatcher()
    intelligence = ProductIntelligenceService()
    updated_products = 0
    linked_items = 0

    async with async_session() as session:
        # 1) Fill aliases/categories for existing products in batches.
        products_stmt = (
            select(Product)
            .options(selectinload(Product.receipt_items))
            .limit(batch_size)
        )
        products_result = await session.execute(products_stmt)
        products = list(products_result.scalars().all())

        for product in products:
            sample_names = {product.canonical_name}
            sample_names.update(product.aliases or [])
            sample_names.update(
                item.name_on_receipt
                for item in product.receipt_items[:5]
                if item.name_on_receipt
            )
            enriched = await intelligence.enrich_items(list(sample_names))
            best = enriched.get(product.canonical_name)
            if not best:
                continue

            if (
                best.canonical_name_en
                and best.canonical_name_en != product.canonical_name
            ):
                product.canonical_name = best.canonical_name_en
                updated_products += 1

            current_aliases = list(product.aliases or [])
            current_aliases_lc = {a.lower() for a in current_aliases}
            for item in enriched.values():
                for alias in item.aliases_en:
                    if (
                        alias.lower() not in current_aliases_lc
                        and len(current_aliases) < 50
                    ):
                        current_aliases.append(alias)
                        current_aliases_lc.add(alias.lower())
                        updated_products += 1
            product.aliases = current_aliases

            if product.category_id is None:
                resolved_product, _ = await matcher.find_or_create_product(
                    product.canonical_name,
                    session,
                    item_intelligence=best,
                )
                if resolved_product.category_id:
                    product.category_id = resolved_product.category_id
                    updated_products += 1

        # 2) Link orphan receipt items.
        orphan_stmt = (
            select(ReceiptItem)
            .where(ReceiptItem.product_id.is_(None))
            .limit(batch_size)
        )
        orphan_result = await session.execute(orphan_stmt)
        orphans = list(orphan_result.scalars().all())

        by_name: dict[str, list[ReceiptItem]] = defaultdict(list)
        for item in orphans:
            by_name[item.name_on_receipt].append(item)

        enriched_orphans = await intelligence.enrich_items(list(by_name.keys()))
        for name, items in by_name.items():
            product, _ = await matcher.find_or_create_product(
                name,
                session,
                item_intelligence=enriched_orphans.get(name),
            )
            for item in items:
                item.product_id = product.id
                linked_items += 1

        if dry_run:
            await session.rollback()
            logger.info(
                "Dry run complete. Product updates=%d, linked receipt_items=%d",
                updated_products,
                linked_items,
            )
        else:
            await session.commit()
            logger.info(
                "Reprocessing complete. Product updates=%d, linked receipt_items=%d",
                updated_products,
                linked_items,
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill product intelligence")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist changes")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Max rows to process for products and orphan items",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_reprocess(dry_run=args.dry_run, batch_size=args.batch_size))
