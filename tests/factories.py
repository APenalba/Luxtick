"""Factory functions for creating ORM test objects with sensible defaults."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Category,
    Discount,
    Product,
    Receipt,
    ReceiptItem,
    ShoppingList,
    ShoppingListItem,
    Store,
    User,
)


def make_user(
    telegram_id: int = 111222333,
    username: str = "testuser",
    first_name: str = "Test",
    **kwargs,
) -> User:
    return User(
        id=kwargs.pop("id", uuid.uuid4()),
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        language=kwargs.pop("language", "en"),
        currency=kwargs.pop("currency", "EUR"),
        timezone=kwargs.pop("timezone", "UTC"),
        **kwargs,
    )


def make_store(
    name: str = "Mercadona",
    **kwargs,
) -> Store:
    normalized = kwargs.pop("normalized_name", name.strip().lower().replace("'", ""))
    return Store(
        id=kwargs.pop("id", uuid.uuid4()),
        name=name,
        normalized_name=normalized,
        **kwargs,
    )


def make_category(
    name: str = "Uncategorized",
    parent_id: uuid.UUID | None = None,
    **kwargs,
) -> Category:
    return Category(
        id=kwargs.pop("id", uuid.uuid4()),
        name=name,
        parent_id=parent_id,
        **kwargs,
    )


def make_product(
    canonical_name: str = "Generic Product",
    aliases: list[str] | None = None,
    category_id: uuid.UUID | None = None,
    **kwargs,
) -> Product:
    return Product(
        id=kwargs.pop("id", uuid.uuid4()),
        canonical_name=canonical_name,
        aliases=aliases or [canonical_name],
        category_id=category_id,
        **kwargs,
    )


def make_receipt(
    user_id: uuid.UUID | None = None,
    store_id: uuid.UUID | None = None,
    total_amount: float = 25.50,
    purchase_date: date | None = None,
    **kwargs,
) -> Receipt:
    return Receipt(
        id=kwargs.pop("id", uuid.uuid4()),
        user_id=user_id or uuid.uuid4(),
        store_id=store_id,
        purchase_date=purchase_date or date.today(),
        total_amount=Decimal(str(total_amount)),
        currency=kwargs.pop("currency", "EUR"),
        **kwargs,
    )


def make_receipt_item(
    receipt_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    name_on_receipt: str = "CHICKEN BREAST",
    quantity: float = 1.0,
    unit_price: float = 5.99,
    total_price: float | None = None,
    **kwargs,
) -> ReceiptItem:
    return ReceiptItem(
        id=kwargs.pop("id", uuid.uuid4()),
        receipt_id=receipt_id or uuid.uuid4(),
        product_id=product_id,
        name_on_receipt=name_on_receipt,
        quantity=Decimal(str(quantity)),
        unit_price=Decimal(str(unit_price)),
        total_price=Decimal(
            str(total_price if total_price is not None else quantity * unit_price)
        ),
        **kwargs,
    )


def make_discount(
    store_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    discount_type: str = "percentage",
    value: float = 20.0,
    **kwargs,
) -> Discount:
    return Discount(
        id=kwargs.pop("id", uuid.uuid4()),
        store_id=store_id,
        product_id=product_id,
        discount_type=discount_type,
        value=Decimal(str(value)),
        start_date=kwargs.pop("start_date", date.today()),
        end_date=kwargs.pop("end_date", None),
        **kwargs,
    )


def make_shopping_list(
    user_id: uuid.UUID | None = None,
    name: str = "Weekly Groceries",
    is_active: bool = True,
    **kwargs,
) -> ShoppingList:
    return ShoppingList(
        id=kwargs.pop("id", uuid.uuid4()),
        user_id=user_id or uuid.uuid4(),
        name=name,
        is_active=is_active,
        **kwargs,
    )


def make_shopping_list_item(
    list_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    custom_name: str = "Milk",
    quantity: float = 1.0,
    **kwargs,
) -> ShoppingListItem:
    return ShoppingListItem(
        id=kwargs.pop("id", uuid.uuid4()),
        list_id=list_id or uuid.uuid4(),
        product_id=product_id,
        custom_name=custom_name,
        quantity=Decimal(str(quantity)),
        is_checked=kwargs.pop("is_checked", False),
        **kwargs,
    )


async def seed_test_data(session: AsyncSession) -> dict:
    """Populate the test DB with a realistic dataset. Returns dict of created objects."""
    # User
    user = make_user(telegram_id=111222333, username="testuser", first_name="Test")
    session.add(user)

    # Stores
    mercadona = make_store(name="Mercadona", normalized_name="mercadona")
    lidl = make_store(name="Lidl", normalized_name="lidl")
    carrefour = make_store(name="Carrefour", normalized_name="carrefour")
    for s in [mercadona, lidl, carrefour]:
        session.add(s)

    # Categories
    meat = make_category(name="Meat")
    poultry = make_category(name="Poultry", parent_id=meat.id)
    dairy = make_category(name="Dairy")
    bakery = make_category(name="Bakery")
    beverages = make_category(name="Beverages")
    produce = make_category(name="Produce")
    for c in [meat, poultry, dairy, bakery, beverages, produce]:
        session.add(c)

    # Products
    chicken = make_product(
        canonical_name="Chicken Breast",
        aliases=["Chicken Breast", "PECH POLLO"],
        category_id=poultry.id,
    )
    milk = make_product(
        canonical_name="Whole Milk",
        aliases=["Whole Milk", "LECHE ENTERA"],
        category_id=dairy.id,
    )
    bread = make_product(
        canonical_name="Bread", aliases=["Bread", "PAN BARRA"], category_id=bakery.id
    )
    oj = make_product(
        canonical_name="Orange Juice",
        aliases=["Orange Juice", "ZUMO NARANJA"],
        category_id=beverages.id,
    )
    apples = make_product(
        canonical_name="Apples", aliases=["Apples", "MANZANAS"], category_id=produce.id
    )
    eggs = make_product(
        canonical_name="Eggs", aliases=["Eggs", "HUEVOS"], category_id=dairy.id
    )
    yogurt = make_product(
        canonical_name="Yogurt", aliases=["Yogurt", "YOGUR"], category_id=dairy.id
    )
    rice = make_product(
        canonical_name="Rice", aliases=["Rice", "ARROZ"], category_id=None
    )
    pasta = make_product(
        canonical_name="Pasta", aliases=["Pasta", "PASTA"], category_id=None
    )
    olive_oil = make_product(
        canonical_name="Olive Oil",
        aliases=["Olive Oil", "ACEITE OLIVA"],
        category_id=None,
    )
    products = [chicken, milk, bread, oj, apples, eggs, yogurt, rice, pasta, olive_oil]
    for p in products:
        session.add(p)

    await session.flush()

    # Receipts + items (8 receipts over last 2 months)
    today = date.today()
    receipts_data = [
        (
            mercadona,
            today - timedelta(days=3),
            [
                (chicken, "Chicken Breast", 1, 5.99),
                (bread, "Bread", 2, 1.20),
                (milk, "Whole Milk", 1, 1.10),
            ],
            Decimal("9.49"),
        ),
        (
            mercadona,
            today - timedelta(days=10),
            [
                (eggs, "Eggs", 1, 2.50),
                (yogurt, "Yogurt", 3, 0.85),
                (oj, "Orange Juice", 1, 2.30),
            ],
            Decimal("7.35"),
        ),
        (
            lidl,
            today - timedelta(days=7),
            [
                (chicken, "PECH POLLO", 2, 4.99),
                (rice, "Rice", 1, 1.89),
                (pasta, "Pasta", 2, 1.15),
            ],
            Decimal("14.17"),
        ),
        (
            lidl,
            today - timedelta(days=20),
            [
                (apples, "Apples", 1.5, 2.49),
                (milk, "LECHE ENTERA", 2, 0.99),
            ],
            Decimal("5.72"),
        ),
        (
            carrefour,
            today - timedelta(days=14),
            [
                (olive_oil, "Olive Oil", 1, 6.50),
                (bread, "PAN BARRA", 1, 1.40),
            ],
            Decimal("7.90"),
        ),
        (
            mercadona,
            today - timedelta(days=35),
            [
                (chicken, "Chicken Breast", 1, 6.20),
                (milk, "Whole Milk", 1, 1.10),
            ],
            Decimal("7.30"),
        ),
        (
            lidl,
            today - timedelta(days=45),
            [
                (eggs, "Eggs", 2, 2.40),
                (apples, "Apples", 1, 2.49),
            ],
            Decimal("7.29"),
        ),
        (
            carrefour,
            today - timedelta(days=50),
            [
                (pasta, "Pasta", 3, 1.10),
                (rice, "Rice", 1, 1.95),
            ],
            Decimal("5.25"),
        ),
    ]

    all_receipts = []
    all_items = []
    for store, r_date, items_data, total in receipts_data:
        receipt = make_receipt(
            user_id=user.id,
            store_id=store.id,
            total_amount=float(total),
            purchase_date=r_date,
        )
        session.add(receipt)
        await session.flush()
        all_receipts.append(receipt)
        for product, name, qty, price in items_data:
            item = make_receipt_item(
                receipt_id=receipt.id,
                product_id=product.id,
                name_on_receipt=name,
                quantity=qty,
                unit_price=price,
                total_price=qty * price,
            )
            session.add(item)
            all_items.append(item)

    # Discounts
    active_discount = make_discount(
        store_id=mercadona.id,
        product_id=chicken.id,
        discount_type="percentage",
        value=20.0,
        end_date=today + timedelta(days=5),
    )
    expired_discount = make_discount(
        store_id=lidl.id,
        product_id=milk.id,
        discount_type="fixed",
        value=0.50,
        start_date=today - timedelta(days=30),
        end_date=today - timedelta(days=10),
    )
    perpetual_discount = make_discount(
        store_id=carrefour.id,
        product_id=None,
        discount_type="percentage",
        value=10.0,
        end_date=None,
        description="Store-wide 10% off",
    )
    for d in [active_discount, expired_discount, perpetual_discount]:
        session.add(d)

    # Shopping lists
    active_list = make_shopping_list(
        user_id=user.id, name="Weekly Groceries", is_active=True
    )
    archived_list = make_shopping_list(
        user_id=user.id, name="Old List", is_active=False
    )
    session.add(active_list)
    session.add(archived_list)
    await session.flush()

    for product, name in [
        (milk, "Milk"),
        (bread, "Bread"),
        (eggs, "Eggs"),
        (chicken, "Chicken"),
    ]:
        item = make_shopping_list_item(
            list_id=active_list.id, product_id=product.id, custom_name=name
        )
        session.add(item)

    await session.flush()

    return {
        "user": user,
        "stores": {"mercadona": mercadona, "lidl": lidl, "carrefour": carrefour},
        "categories": {
            "meat": meat,
            "poultry": poultry,
            "dairy": dairy,
            "bakery": bakery,
            "beverages": beverages,
            "produce": produce,
        },
        "products": {p.canonical_name.lower().replace(" ", "_"): p for p in products},
        "receipts": all_receipts,
        "items": all_items,
        "discounts": {
            "active": active_discount,
            "expired": expired_discount,
            "perpetual": perpetual_discount,
        },
        "shopping_lists": {"active": active_list, "archived": archived_list},
    }
