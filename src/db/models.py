"""SQLAlchemy ORM models for the LuxTick database."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class User(Base):
    """A Telegram user who interacts with the bot."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="en")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    shopping_lists: Mapped[list["ShoppingList"]] = relationship(
        back_populates="user", lazy="selectin"
    )


class Store(Base):
    """A retail store where purchases are made."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    store_type: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="store", lazy="selectin"
    )
    discounts: Mapped[list["Discount"]] = relationship(
        back_populates="store", lazy="selectin"
    )


class Category(Base):
    """A hierarchical product category (e.g., Meat > Poultry > Chicken)."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), index=True
    )

    # Relationships
    parent: Mapped["Category | None"] = relationship(
        back_populates="children", remote_side="Category.id", lazy="selectin"
    )
    children: Mapped[list["Category"]] = relationship(
        back_populates="parent", lazy="selectin"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="category", lazy="selectin"
    )


class Product(Base):
    """A canonical product entry with aliases for fuzzy matching."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), index=True
    )
    default_unit: Mapped[str | None] = mapped_column(String(50))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), default=list)

    # Relationships
    category: Mapped["Category | None"] = relationship(
        back_populates="products", lazy="selectin"
    )
    receipt_items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="product", lazy="selectin"
    )
    discounts: Mapped[list["Discount"]] = relationship(
        back_populates="product", lazy="selectin"
    )
    shopping_list_items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="product", lazy="selectin"
    )


class Receipt(Base):
    """A purchase event linking a user to a store on a specific date."""

    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), index=True
    )
    purchase_date: Mapped[date] = mapped_column(Date)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    image_url: Mapped[str | None] = mapped_column(String(1000))
    raw_extracted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="receipts", lazy="selectin")
    store: Mapped["Store | None"] = relationship(
        back_populates="receipts", lazy="selectin"
    )
    items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="receipt", lazy="selectin", cascade="all, delete-orphan"
    )


class ReceiptItem(Base):
    """A single line item on a receipt."""

    __tablename__ = "receipt_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    name_on_receipt: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=1)
    unit: Mapped[str | None] = mapped_column(String(50))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    discount_type: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    receipt: Mapped["Receipt"] = relationship(back_populates="items", lazy="selectin")
    product: Mapped["Product | None"] = relationship(
        back_populates="receipt_items", lazy="selectin"
    )


class Discount(Base):
    """A known discount or offer at a store."""

    __tablename__ = "discounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), index=True
    )
    discount_type: Mapped[str] = mapped_column(
        String(50)
    )  # percentage, fixed, bogo, etc.
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    store: Mapped["Store | None"] = relationship(
        back_populates="discounts", lazy="selectin"
    )
    product: Mapped["Product | None"] = relationship(
        back_populates="discounts", lazy="selectin"
    )


class ShoppingList(Base):
    """A named shopping list belonging to a user."""

    __tablename__ = "shopping_lists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="shopping_lists", lazy="selectin"
    )
    items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="shopping_list", lazy="selectin", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    """An item on a shopping list."""

    __tablename__ = "shopping_list_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    custom_name: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=1)
    unit: Mapped[str | None] = mapped_column(String(50))
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship(
        back_populates="items", lazy="selectin"
    )
    product: Mapped["Product | None"] = relationship(
        back_populates="shopping_list_items", lazy="selectin"
    )
