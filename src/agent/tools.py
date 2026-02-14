"""Tool definitions for the LLM agent.

Each tool is defined as a dict following the OpenAI function-calling schema,
which LiteLLM translates to the appropriate format for each provider.
"""

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # DATA RETRIEVAL TOOLS
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "search_purchases",
            "description": (
                "Search the user's purchase history. Returns matching receipt items "
                "with store, date, product, price, and quantity. Use this for questions "
                "like 'what did I buy at Mercadona last week?' or 'show me all chicken purchases'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free-text search term for product names (e.g., 'chicken', 'milk').",
                    },
                    "store": {
                        "type": "string",
                        "description": "Filter by store name (e.g., 'Mercadona', 'Lidl').",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by product category (e.g., 'Meat', 'Dairy').",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for the search range (ISO format: YYYY-MM-DD).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for the search range (ISO format: YYYY-MM-DD).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default 20.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": (
                "Get aggregated spending statistics. Returns totals and breakdowns. "
                "Use this for questions like 'how much did I spend this month?' or "
                "'how much at Mercadona in January?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": (
                            "Time period: 'today', 'this_week', 'this_month', 'last_month', "
                            "'this_year', or a custom range using start_date/end_date."
                        ),
                    },
                    "group_by": {
                        "type": "string",
                        "enum": [
                            "store",
                            "category",
                            "product",
                            "day",
                            "week",
                            "month",
                        ],
                        "description": "How to group the spending breakdown.",
                    },
                    "store": {
                        "type": "string",
                        "description": "Filter to a specific store.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter to a specific category.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Custom period start date (ISO format: YYYY-MM-DD).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Custom period end date (ISO format: YYYY-MM-DD).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_frequent_purchases",
            "description": (
                "Get the most frequently purchased products in a given period. "
                "Use this for questions like 'what do I usually buy weekly?' or "
                "'my most common purchases'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": (
                            "Time period to analyze: 'last_week', 'last_month', "
                            "'last_3_months', 'last_year', 'all_time'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of top products to return. Default 10.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_prices",
            "description": (
                "Compare prices of a product across different stores or over time. "
                "Use this for questions like 'where is chicken cheapest?' or "
                "'has milk price gone up?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {
                        "type": "string",
                        "description": "The product to compare (e.g., 'chicken breast').",
                    },
                    "store": {
                        "type": "string",
                        "description": "Optionally limit comparison to a specific store.",
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period for comparison. Default 'last_3_months'.",
                    },
                },
                "required": ["product"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_history",
            "description": (
                "Get the full purchase history for a specific product, including "
                "every time it was bought, where, and at what price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {
                        "type": "string",
                        "description": "The product name to look up.",
                    },
                },
                "required": ["product"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_discounts",
            "description": (
                "Get currently active discounts and offers. "
                "Use this for questions like 'any deals at Lidl?' or 'discounts on chicken?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "description": "Filter by store name.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by product category.",
                    },
                },
                "required": [],
            },
        },
    },
    # -------------------------------------------------------------------------
    # DATA ENTRY TOOLS
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "add_manual_purchase",
            "description": (
                "Add a purchase manually. Use this when the user tells you about a "
                "purchase without a receipt photo. E.g., 'I bought chicken for 5.99 "
                "and bread for 1.20 at Mercadona today'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "description": "Store name where the purchase was made.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Purchase date in ISO format (YYYY-MM-DD). Defaults to today.",
                    },
                    "items": {
                        "type": "array",
                        "description": "List of purchased items.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Product name.",
                                },
                                "quantity": {
                                    "type": "number",
                                    "description": "Quantity purchased. Default 1.",
                                },
                                "unit_price": {
                                    "type": "number",
                                    "description": "Price per unit.",
                                },
                                "total_price": {
                                    "type": "number",
                                    "description": "Total price for this item (quantity * unit_price).",
                                },
                            },
                            "required": ["name", "unit_price"],
                        },
                    },
                    "total": {
                        "type": "number",
                        "description": "Total purchase amount. If not provided, sum of item totals is used.",
                    },
                },
                "required": ["store", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_discount",
            "description": (
                "Register a discount or offer at a store. Use this when the user "
                "reports a deal, e.g., 'Chicken is 20% off at Mercadona until Friday'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "description": "Store offering the discount.",
                    },
                    "product": {
                        "type": "string",
                        "description": "Product the discount applies to (optional for store-wide).",
                    },
                    "discount_type": {
                        "type": "string",
                        "enum": ["percentage", "fixed", "bogo", "multi_buy"],
                        "description": "Type of discount.",
                    },
                    "value": {
                        "type": "number",
                        "description": "Discount value (e.g., 20 for 20%, or 1.50 for 1.50 EUR off).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of the offer.",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Discount start date (ISO format). Defaults to today.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Discount end date (ISO format).",
                    },
                },
                "required": ["store", "discount_type", "value"],
            },
        },
    },
    # -------------------------------------------------------------------------
    # SHOPPING LIST TOOLS
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "create_shopping_list",
            "description": (
                "Create a new shopping list with optional initial items. "
                "E.g., 'Create a shopping list for the weekend with milk, eggs, and bread'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the shopping list (e.g., 'Weekend groceries').",
                    },
                    "items": {
                        "type": "array",
                        "description": "Initial items to add.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Item name.",
                                },
                                "quantity": {
                                    "type": "number",
                                    "description": "Quantity needed. Default 1.",
                                },
                                "unit": {
                                    "type": "string",
                                    "description": "Unit (e.g., 'kg', 'pcs', 'liters').",
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Additional notes for this item.",
                                },
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_shopping_list",
            "description": (
                "Update an existing shopping list: add items, remove items, or check items off."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the shopping list to update.",
                    },
                    "add_items": {
                        "type": "array",
                        "description": "Items to add to the list.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "quantity": {"type": "number"},
                                "unit": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "remove_items": {
                        "type": "array",
                        "description": "Item names to remove from the list.",
                        "items": {"type": "string"},
                    },
                    "check_items": {
                        "type": "array",
                        "description": "Item names to mark as checked/bought.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["list_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shopping_lists",
            "description": "Get the user's shopping lists with their items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "If true, only return active (non-archived) lists. Default true.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_shopping_list",
            "description": (
                "Suggest a shopping list based on the user's purchase patterns. "
                "Analyzes frequently bought items to suggest what they might need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "based_on": {
                        "type": "string",
                        "enum": ["weekly_habits", "monthly_habits", "running_low"],
                        "description": "What to base suggestions on. Default 'weekly_habits'.",
                    },
                },
                "required": [],
            },
        },
    },
    # -------------------------------------------------------------------------
    # ADVANCED ANALYTICS
    # -------------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "run_analytics_query",
            "description": (
                "Run a complex analytical query that the other tools can't handle. "
                "Provide a natural language description of the question, and a SQL query "
                "will be generated and executed read-only against the database. Use this as "
                "a LAST RESORT when no other tool fits the question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language description of the analytical question.",
                    },
                    "sql_query": {
                        "type": "string",
                        "description": (
                            "A read-only SQL SELECT query to execute. Must be a SELECT statement. "
                            "Available tables: users, stores, categories, products, receipts, "
                            "receipt_items, discounts, shopping_lists, shopping_list_items. "
                            "Key columns: receipts.purchase_date, receipts.total_amount, "
                            "receipt_items.name_on_receipt, receipt_items.total_price, "
                            "stores.name, products.canonical_name, categories.name."
                        ),
                    },
                },
                "required": ["question", "sql_query"],
            },
        },
    },
]
