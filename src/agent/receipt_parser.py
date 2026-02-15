"""Receipt parsing pipeline: extracts structured data from receipt photos using GPT-4o vision."""

import base64
import json
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import litellm
from pydantic import BaseModel, Field

from src.config import settings
from src.db.models import Receipt, ReceiptItem, User
from src.db.session import async_session
from src.services.product import ProductMatcher
from src.services.purchase import PurchaseService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas for the structured receipt extraction
# ---------------------------------------------------------------------------


class ExtractedItem(BaseModel):
    """A single item extracted from a receipt."""

    name: str = Field(description="Product name as printed on the receipt")
    quantity: float = Field(default=1.0, description="Quantity purchased")
    unit: str | None = Field(
        default=None, description="Unit of measurement if applicable"
    )
    unit_price: float = Field(description="Price per unit")
    total_price: float = Field(description="Total price for this line item")
    discount_amount: float | None = Field(
        default=None, description="Discount amount if any"
    )
    discount_type: str | None = Field(
        default=None, description="Type of discount (percentage, fixed, etc.)"
    )


class ExtractedReceipt(BaseModel):
    """Structured data extracted from a receipt image."""

    store_name: str = Field(description="Name of the store/business")
    store_address: str | None = Field(
        default=None, description="Store address if visible"
    )
    purchase_date: str | None = Field(
        default=None, description="Purchase date in ISO format (YYYY-MM-DD)"
    )
    items: list[ExtractedItem] = Field(description="List of purchased items")
    subtotal: float | None = Field(default=None, description="Subtotal before tax")
    tax: float | None = Field(default=None, description="Tax amount")
    total: float = Field(description="Final total amount")
    currency: str = Field(default="EUR", description="Currency code")
    confidence_notes: list[str] = Field(
        default_factory=list,
        description="Any items the model was uncertain about",
    )


# ---------------------------------------------------------------------------
# Vision extraction prompt
# ---------------------------------------------------------------------------

RECEIPT_EXTRACTION_PROMPT = """You are an expert receipt OCR and data extraction specialist with 10+ years experience processing receipts from global retailers including Europe. You excel at accurately identifying logical line items even when products span multiple printed lines.

CRITICAL RULES - Follow EXACTLY to ensure perfect extraction:

1. **SINGLE ITEM PER ENTRY**: Products often wrap across 2-4 lines (e.g., "POWER MULTI [EXT: BLUETOOTH] 1"). Group ALL related lines into ONE logical item. Never split multi-line descriptions.

2. **IGNORE NON-PRODUCT LINES**: Exclude:
   - Store headers/names/numbers
   - Phone numbers, addresses, barcodes
   - Reference codes (e.g., "46098", "17.59")
   - Tax/VAT lines, subtotals, totals
   - Payment method lines
   - Promo/disclaimers
   - Timestamps, URLs
   - Footer text like "RETURZ 30 JOURS"

3. **STORE NAME**: Extract ONLY commercial brand (e.g., "Mediamarkt", "Cactus", "Aldi", "Lidl"). Remove S.L., S.A., city names, "City Market", phone numbers.

4. **ITEM IDENTIFICATION**: A line item contains:
   - Product description (possibly multi-line)
   - Quantity (usually 1 if absent)
   - Unit price
   - Line total
   
   Example from similar receipt:
   Input lines: "POWER MULTI [EXT: BLUETOOTH] 1"
   → ONE item: name="POWER MULTI [EXT: BLUETOOTH]", qty=1, unit=17.59, total=17.59

5. **NUMBERS ALIGNMENT**: Use visual/spatial alignment. Prices right-aligned, quantities before prices.

6. **DATE**: Parse European format DD.MM.YYYY from footer/header. Use most likely: 25.02.2024 → "2024-02-25"

7. **AMBIGUOUS**: Use null + note in confidence_notes.

## STEP-BY-STEP PROCESS:
1. Scan receipt top-to-bottom
2. Identify header (store, date)
3. Locate product section (indented/multi-line descriptions)
4. Group each logical product + qty + price + total → 1 item
5. Find subtotal/tax/total lines
6. Extract footer info

## REQUIRED JSON OUTPUT - EXACTLY (no extra text):
```json
{
  "store_name": "string",
  "store_address": "string or null",
  "purchase_date": "YYYY-MM-DD or null",
  "items": [
    {
      "name": "string",
      "quantity": 1.0,
      "unit": "string or null",
      "unit_price": 0.00,
      "total_price": 0.00,
      "discount_amount": null,
      "discount_type": null
    }
  ],
  "subtotal": null,
  "tax": null,
  "total": 0.00,
  "currency": "EUR",
  "confidence_notes": []
}
```

## EXAMPLE 1 - Multi-line item:
Receipt lines:
```
COCA COLA
ZERO 33CL
1   1.29   1.29
```
→ {"name": "COCA COLA ZERO 33CL", "quantity":1.0, "unit_price":1.29, "total_price":1.29}

## EXAMPLE 2 - Reference code exclusion:
```
REF: 123456
CHIPS 2PK  2.49  2.49
```
→ Ignore REF, extract only CHIPS item.

ANALYZE THIS RECEIPT IMAGE AND OUTPUT ONLY VALID JSON."""


class ReceiptParser:
    """Parses receipt images using GPT-4o vision and stores the results."""

    def __init__(self) -> None:
        self.product_matcher = ProductMatcher()
        self.purchase_service = PurchaseService()

    async def extract_from_image(self, image_data: bytes) -> ExtractedReceipt:
        """Send a receipt image to GPT-4o vision and extract structured data.

        Args:
            image_data: Raw bytes of the receipt image.

        Returns:
            Parsed receipt data as an ExtractedReceipt model.
        """
        # Encode image to base64
        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Determine image type (assume JPEG for photos from Telegram)
        image_url = f"data:image/jpeg;base64,{b64_image}"

        logger.info("Sending receipt image to vision model for extraction...")

        response = await litellm.acompletion(
            model=settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RECEIPT_EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "high"},
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=4096,
        )

        raw_content = response.choices[0].message.content
        logger.debug("Vision model raw response: %s", raw_content[:500])

        # Parse the JSON response
        # Strip markdown code fences if present
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            extracted = ExtractedReceipt(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse vision model response: %s", e)
            raise ValueError(
                f"Could not parse the receipt data from the image. Error: {e}"
            ) from e

        logger.info(
            "Extracted receipt: store=%s, items=%d, total=%.2f",
            extracted.store_name,
            len(extracted.items),
            extracted.total,
        )

        return extracted

    async def parse_and_store(
        self,
        user: User,
        image_data: bytes,
    ) -> str:
        """Full pipeline: extract from image, match products, store in DB, return summary.

        Args:
            user: The database User.
            image_data: Raw receipt image bytes.

        Returns:
            A formatted summary string to send to the user.
        """
        # Step 1: Extract structured data from the image
        extracted = await self.extract_from_image(image_data)

        # Step 2: Store in database
        async with async_session() as session:
            # Find or create store
            store = await self.purchase_service._get_or_create_store(
                extracted.store_name, session
            )

            # Parse date
            purchase_date = (
                date.fromisoformat(extracted.purchase_date)
                if extracted.purchase_date
                else date.today()
            )

            # Create receipt
            receipt = Receipt(
                id=uuid.uuid4(),
                user_id=user.id,
                store_id=store.id,
                purchase_date=purchase_date,
                total_amount=Decimal(str(extracted.total)),
                currency=extracted.currency,
            )
            session.add(receipt)
            await session.flush()

            # Step 3: Match items to canonical products and create receipt items
            matched_items: list[dict[str, Any]] = []
            for item in extracted.items:
                product, is_new = await self.product_matcher.find_or_create_product(
                    item.name, session
                )

                receipt_item = ReceiptItem(
                    id=uuid.uuid4(),
                    receipt_id=receipt.id,
                    product_id=product.id,
                    name_on_receipt=item.name,
                    quantity=Decimal(str(item.quantity)),
                    unit=item.unit,
                    unit_price=Decimal(str(item.unit_price)),
                    total_price=Decimal(str(item.total_price)),
                    discount_amount=(
                        Decimal(str(item.discount_amount))
                        if item.discount_amount
                        else None
                    ),
                    discount_type=item.discount_type,
                )
                session.add(receipt_item)

                matched_items.append(
                    {
                        "name": item.name,
                        "canonical": product.canonical_name,
                        "is_new": is_new,
                        "qty": item.quantity,
                        "price": item.total_price,
                    }
                )

            await session.commit()

        # Step 4: Build summary for user
        summary = self._build_summary(
            store_name=store.name,
            purchase_date=purchase_date,
            items=matched_items,
            total=extracted.total,
            currency=extracted.currency,
            confidence_notes=extracted.confidence_notes,
            receipt_id=str(receipt.id),
        )

        return summary

    def _build_summary(
        self,
        store_name: str,
        purchase_date: date,
        items: list[dict[str, Any]],
        total: float,
        currency: str,
        confidence_notes: list[str],
        receipt_id: str,
    ) -> str:
        """Build a user-facing summary of the parsed receipt."""
        lines = [
            "**Receipt parsed successfully!**\n",
            f"**Store:** {store_name}",
            f"**Date:** {purchase_date.isoformat()}",
            f"**Items:** {len(items)}",
            "",
        ]

        for item in items:
            qty_str = f"{item['qty']}x " if item["qty"] != 1 else ""
            new_badge = " (new product)" if item["is_new"] else ""
            lines.append(
                f"- {qty_str}{item['name']} -- {item['price']:.2f} {currency}{new_badge}"
            )

        lines.append(f"\n**Total: {total:.2f} {currency}**")

        if confidence_notes:
            lines.append("\n_Notes:_")
            for note in confidence_notes:
                lines.append(f"- _{note}_")

        lines.append(f"\nReceipt ID: `{receipt_id[:8]}...`")
        lines.append("If anything looks wrong, just tell me what to correct!")

        return "\n".join(lines)
