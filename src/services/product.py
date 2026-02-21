"""Product matching and canonical product management."""

import logging
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category, Product
from src.db.session import async_session
from src.services.category_taxonomy import resolve_or_create_category_path
from src.services.product_intelligence import ItemIntelligence

logger = logging.getLogger(__name__)

# Minimum fuzzy match score to auto-link a receipt item to a canonical product
AUTO_MATCH_THRESHOLD = 80


@dataclass(slots=True)
class ProductResolution:
    """Result of resolving a query term into canonical products."""

    product_ids: list[uuid.UUID]
    matched_terms: list[str]


class ProductMatcher:
    """Fuzzy-matches receipt item names to canonical products in the database."""

    async def find_or_create_product(
        self,
        name_on_receipt: str,
        session: AsyncSession | None = None,
        item_intelligence: ItemIntelligence | None = None,
    ) -> tuple[Product, bool]:
        """Find a matching canonical product or create a new one.

        Args:
            name_on_receipt: The product name as printed on the receipt.
            session: Optional existing session. If None, creates a new one.

        Returns:
            Tuple of (product, is_new) where is_new indicates if a new product was created.
        """
        manage_session = session is None
        if manage_session:
            session = async_session()
            await session.__aenter__()

        assert session is not None

        try:
            # Load all products for fuzzy matching
            stmt = select(Product)
            result = await session.execute(stmt)
            products: list[Product] = list(result.scalars().all())

            if not products:
                # No products exist yet -- create a new one
                product = await self._create_product(
                    name_on_receipt,
                    session,
                    item_intelligence=item_intelligence,
                )
                if manage_session:
                    await session.commit()
                return product, True

            # Build a list of (name, product) for matching against canonical names + aliases
            candidates: list[tuple[str, Product]] = []
            for p in products:
                candidates.append((p.canonical_name, p))
                if p.aliases:
                    for alias in p.aliases:
                        candidates.append((alias, p))

            candidate_names = [c[0] for c in candidates]

            target_name = (
                item_intelligence.canonical_name_en
                if item_intelligence and item_intelligence.canonical_name_en
                else name_on_receipt
            )

            # Fuzzy match (explicit processor for case-insensitive comparison)
            match = process.extractOne(
                target_name,
                candidate_names,
                scorer=fuzz.token_sort_ratio,
                processor=default_process,
            )

            if match and match[1] >= AUTO_MATCH_THRESHOLD:
                matched_name = match[0]
                matched_product = next(p for n, p in candidates if n == matched_name)
                logger.info(
                    "Matched '%s' -> '%s' (score: %d)",
                    target_name,
                    matched_product.canonical_name,
                    match[1],
                )

                # Add source alias and LLM aliases if they are new.
                if matched_product.aliases is None:
                    matched_product.aliases = []
                existing_aliases = {a.lower() for a in matched_product.aliases}
                candidate_aliases = [name_on_receipt]
                if item_intelligence:
                    candidate_aliases.extend(item_intelligence.aliases_en)

                added_alias = False
                for alias in candidate_aliases:
                    cleaned = alias.strip()
                    if (
                        cleaned
                        and cleaned.lower() not in existing_aliases
                        and len(matched_product.aliases) < 50
                    ):
                        matched_product.aliases = [*matched_product.aliases, cleaned]
                        existing_aliases.add(cleaned.lower())
                        added_alias = True

                category_assigned = False
                if (
                    item_intelligence
                    and item_intelligence.category_path_en
                    and matched_product.category_id is None
                ):
                    matched_product.category_id = await resolve_or_create_category_path(
                        session, item_intelligence.category_path_en
                    )
                    category_assigned = matched_product.category_id is not None

                if (added_alias or category_assigned) and manage_session:
                    await session.commit()

                return matched_product, False

            # No good match -- create a new product
            product = await self._create_product(
                name_on_receipt,
                session,
                item_intelligence=item_intelligence,
            )
            if manage_session:
                await session.commit()
            return product, True

        finally:
            if manage_session:
                await session.__aexit__(None, None, None)

    async def _create_product(
        self,
        name: str,
        session: AsyncSession,
        item_intelligence: ItemIntelligence | None = None,
    ) -> Product:
        """Create a new canonical product from a receipt item name."""
        canonical_name = (
            item_intelligence.canonical_name_en.strip().title()
            if item_intelligence and item_intelligence.canonical_name_en
            else name.strip().title()
        )
        aliases: list[str] = [name]
        if item_intelligence:
            aliases.extend(item_intelligence.aliases_en)
        deduped_aliases = list(
            dict.fromkeys(a.strip() for a in aliases if a and a.strip())
        )[:50]

        category_id: uuid.UUID | None = None
        if item_intelligence and item_intelligence.category_path_en:
            category_id = await resolve_or_create_category_path(
                session,
                item_intelligence.category_path_en,
            )

        product = Product(
            id=uuid.uuid4(),
            canonical_name=canonical_name,
            aliases=deduped_aliases,
            category_id=category_id,
        )
        session.add(product)
        logger.info("Created new product: '%s'", product.canonical_name)
        return product


class ProductResolver:
    """Resolve user query terms to canonical products via aliases and fuzzy fallback."""

    async def resolve_products(
        self,
        term: str,
        session: AsyncSession,
        limit: int = 20,
    ) -> ProductResolution:
        cleaned_term = term.strip()
        if not cleaned_term:
            return ProductResolution(product_ids=[], matched_terms=[])

        stmt = (
            select(Product)
            .join(Category, Product.category_id == Category.id, isouter=True)
            .where(
                or_(
                    Product.canonical_name.ilike(f"%{cleaned_term}%"),
                    Product.aliases.any(cleaned_term),  # type: ignore[arg-type]
                    Category.name.ilike(f"%{cleaned_term}%"),
                )
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        products = list(result.scalars().all())

        if products:
            return ProductResolution(
                product_ids=[p.id for p in products],
                matched_terms=[p.canonical_name for p in products],
            )

        # Fuzzy fallback over canonical names and aliases.
        all_stmt = select(Product)
        all_result = await session.execute(all_stmt)
        all_products = list(all_result.scalars().all())
        if not all_products:
            return ProductResolution(product_ids=[], matched_terms=[])

        candidates: list[tuple[str, Product]] = []
        for product in all_products:
            candidates.append((product.canonical_name, product))
            for alias in product.aliases or []:
                candidates.append((alias, product))

        match = process.extractOne(
            cleaned_term,
            [name for name, _ in candidates],
            scorer=fuzz.token_sort_ratio,
            processor=default_process,
        )
        if not match or match[1] < 75:
            return ProductResolution(product_ids=[], matched_terms=[])

        best_product = next(p for n, p in candidates if n == match[0])
        return ProductResolution(
            product_ids=[best_product.id],
            matched_terms=[best_product.canonical_name],
        )
