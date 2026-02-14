"""Initial database schema.

Revision ID: 001
Revises: None
Create Date: 2026-02-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- Users --
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "telegram_id", sa.BigInteger, unique=True, nullable=False, index=True
        ),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("preferences", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- Stores --
    op.create_table(
        "stores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "normalized_name", sa.String(255), unique=True, nullable=False, index=True
        ),
        sa.Column("store_type", sa.String(100), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
    )

    # -- Categories (self-referencing hierarchy) --
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
            index=True,
        ),
    )

    # -- Products --
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.String(255), nullable=False, index=True),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("default_unit", sa.String(50), nullable=True),
        sa.Column("barcode", sa.String(100), nullable=True, index=True),
        sa.Column("aliases", sa.ARRAY(sa.String(255)), nullable=True),
    )

    # -- Receipts --
    op.create_table(
        "receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stores.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("image_url", sa.String(1000), nullable=True),
        sa.Column("raw_extracted_text", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- Receipt Items --
    op.create_table(
        "receipt_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "receipt_id",
            UUID(as_uuid=True),
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("name_on_receipt", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("discount_type", sa.String(50), nullable=True),
    )

    # -- Discounts --
    op.create_table(
        "discounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stores.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("discount_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- Shopping Lists --
    op.create_table(
        "shopping_lists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- Shopping List Items --
    op.create_table(
        "shopping_list_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "list_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shopping_lists.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("custom_name", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("is_checked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("shopping_list_items")
    op.drop_table("shopping_lists")
    op.drop_table("discounts")
    op.drop_table("receipt_items")
    op.drop_table("receipts")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("stores")
    op.drop_table("users")
