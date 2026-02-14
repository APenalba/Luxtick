"""Product matching and canonical product management."""

import logging
import uuid

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Product
from src.db.session import async_session

logger = logging.getLogger(__name__)

# Minimum fuzzy match score to auto-link a receipt item to a canonical product
AUTO_MATCH_THRESHOLD = 80


class ProductMatcher:
    """Fuzzy-matches receipt item names to canonical products in the database."""

    async def find_or_create_product(
        self,
        name_on_receipt: str,
        session: AsyncSession | None = None,
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
                product = await self._create_product(name_on_receipt, session)
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

            # Fuzzy match (explicit processor for case-insensitive comparison)
            match = process.extractOne(
                name_on_receipt,
                candidate_names,
                scorer=fuzz.token_sort_ratio,
                processor=default_process,
            )

            if match and match[1] >= AUTO_MATCH_THRESHOLD:
                matched_name = match[0]
                matched_product = next(p for n, p in candidates if n == matched_name)
                logger.info(
                    "Matched '%s' -> '%s' (score: %d)",
                    name_on_receipt,
                    matched_product.canonical_name,
                    match[1],
                )

                # Add this receipt name as an alias if it's new
                if matched_product.aliases is None:
                    matched_product.aliases = []
                if name_on_receipt.lower() not in [
                    a.lower() for a in matched_product.aliases
                ]:
                    matched_product.aliases = [
                        *matched_product.aliases,
                        name_on_receipt,
                    ]
                    if manage_session:
                        await session.commit()

                return matched_product, False

            # No good match -- create a new product
            product = await self._create_product(name_on_receipt, session)
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
    ) -> Product:
        """Create a new canonical product from a receipt item name."""
        product = Product(
            id=uuid.uuid4(),
            canonical_name=name.strip().title(),
            aliases=[name],
        )
        session.add(product)
        logger.info("Created new product: '%s'", product.canonical_name)
        return product
