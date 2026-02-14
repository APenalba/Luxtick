# LuxTick - Technical Specification

> Version: 1.0.0
> Date: 2026-02-11
> Status: Implementation Phase

---

## 1. Project Overview

**LuxTick** is an intelligent Telegram bot that serves as a personal purchase, receipt, and shopping list manager. It leverages LLM-powered tool calling to understand natural language queries and interact with a structured PostgreSQL database, eliminating the need for rigid intent classification.

### Key Capabilities

- **Natural language queries**: "How much have I spent on chicken this month?", "What do I usually buy weekly?"
- **Receipt photo parsing**: Upload a receipt photo and the bot extracts all items, prices, store info, and discounts automatically
- **Shopping list management**: Create, update, and get AI-suggested shopping lists based on purchase history
- **Spending analytics**: Breakdowns by store, category, product, and time period
- **Discount tracking**: Register and query active offers and discounts
- **Manual data entry**: Add purchases by hand through conversational input

### Target Users

Primarily a personal tool, designed for open-source distribution so anyone can self-host their own instance.

---

## 2. Architecture

### 2.1 Core Pattern: LLM Agent with Tool Calling

The system uses the **tool-calling agent pattern**. The LLM does NOT access the database directly. Instead:

1. User sends a message via Telegram
2. The bot forwards the message to the LLM along with available tool definitions (JSON schemas)
3. The LLM reasons about which tool(s) to call
4. The bot executes the tool function (which queries the database via SQLAlchemy)
5. Tool results are returned to the LLM
6. The LLM formulates a natural language response
7. The response is sent back to the user via Telegram

This approach avoids rigid intent classification entirely. Adding a new capability means adding a new tool definition -- no retraining, no regex patterns, no decision trees.

### 2.2 Multi-Model Strategy

The architecture uses a model abstraction layer (LiteLLM) enabling model swapping via configuration.

| Task | Model | Rationale |
|------|-------|-----------|
| Conversational AI + Tool Calling | Gemini 2.0 Flash | $0.10/MTok input, $0.40/MTok output. Excellent function calling, 1M context window, fast responses. |
| Receipt Vision Parsing | GPT-4o | 97%+ accuracy on receipt OCR benchmarks. Superior structured extraction from photos. |
| Text-to-SQL (complex queries) | Gemini 2.0 Flash | Handled by the conversational model as part of its tool-calling flow. |

**Why API models over local/self-hosted:**
- At personal usage levels (~100 msgs/day), API costs are 1-5 EUR/month total
- A capable local model (Llama 3.1 70B+) requires a GPU VPS costing 50-200+ EUR/month
- Function calling quality in open-source models lags behind Gemini/GPT/Claude
- The LiteLLM abstraction allows switching to a local model later if economics change

### 2.3 Infrastructure

**Primary deployment: Docker Compose on Hetzner Cloud CX22 VPS** (~4.50 EUR/month, 2 vCPU, 4GB RAM, 40GB SSD)

Components:
- **Bot container**: Python application (aiogram + agent logic)
- **PostgreSQL container**: Data persistence
- **Caddy container**: Reverse proxy for Telegram webhook

CI/CD via GitHub Actions: on push to `main`, build image, run tests, deploy via SSH. Alembic migrations execute automatically on container startup.

---

## 3. Data Model

### 3.1 Entity Descriptions

**Users**: Telegram users who interact with the bot. Identified by their Telegram user ID. Auto-registered on first `/start`.

**Stores**: Retail establishments where purchases are made (e.g., Mercadona, Lidl). Stores have a `normalized_name` for deduplication.

**Categories**: Hierarchical product categories (e.g., Meat > Poultry > Chicken). Self-referencing `parent_id` enables tree queries.

**Products**: Canonical product entries. Each product has a unique canonical name and an `aliases` array for fuzzy matching against receipt line items (e.g., "PECH POLLO" maps to canonical "Chicken Breast").

**Receipts**: A purchase event. Links a user to a store on a date. Optionally stores the original receipt image URL and raw extracted text.

**ReceiptItems**: Individual line items on a receipt. Stores both the raw `name_on_receipt` text and a foreign key to the matched canonical `Product`. Tracks quantity, unit price, total price, and any discount applied.

**Discounts**: Known offers at stores. Can target a specific product, a category, or be store-wide (nullable foreign keys). Tracks discount type (percentage, fixed amount, buy-one-get-one, etc.), value, and validity period.

**ShoppingLists**: Named lists created by users. An `is_active` flag distinguishes current from archived lists.

**ShoppingListItems**: Items on a shopping list. Links to a canonical product (optional -- can use `custom_name` for ad-hoc items). Tracks quantity, unit, checked status, and notes.

### 3.2 Relationships

- User 1:N Receipts
- User 1:N ShoppingLists
- Store 1:N Receipts
- Store 1:N Discounts
- Receipt 1:N ReceiptItems
- Product N:1 Category
- Product 1:N ReceiptItems
- Product 1:N Discounts
- Product 1:N ShoppingListItems
- Category 1:N Categories (self-referencing hierarchy)
- ShoppingList 1:N ShoppingListItems

### 3.3 Key Design Decisions

- **UUIDs** as primary keys for all entities (public-facing, non-sequential)
- **Canonical products with aliases**: Enables fuzzy matching of receipt text to known products
- **Hierarchical categories**: Queries like "how much on Meat?" aggregate across all subcategories
- **Nullable FKs on Discounts**: A discount with only `store_id` set is store-wide; with `product_id` set is product-specific
- **JSONB preferences on Users**: Flexible storage for user settings (currency, timezone, notification prefs)

---

## 4. LLM Tool Definitions

### 4.1 Data Retrieval Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_purchases` | query, start_date, end_date, store, category, product | Search purchase history with flexible filters |
| `get_spending_summary` | period, group_by, store, category | Aggregate spending stats by store/category/product/time |
| `get_frequent_purchases` | period, limit | What does the user usually buy in a given period |
| `compare_prices` | product, store, period | Price trends for a product across stores and time |
| `get_product_history` | product | Full purchase history for a specific product |
| `get_active_discounts` | store, category | Currently known discounts and offers |

### 4.2 Data Entry Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `add_manual_purchase` | store, date, items | Add a purchase manually |
| `confirm_receipt_data` | receipt_id, corrections | Confirm or correct parsed receipt data |
| `register_discount` | store, product, type, value, dates | Register a discount or offer |

### 4.3 Shopping List Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_shopping_list` | name, items | Create a new shopping list |
| `update_shopping_list` | list_id, add_items, remove_items, check_items | Modify an existing list |
| `get_shopping_lists` | active_only | Retrieve current shopping lists |
| `suggest_shopping_list` | based_on | AI-suggested list based on purchase patterns |

### 4.4 Advanced Analytics Tool

| Tool | Parameters | Description |
|------|-----------|-------------|
| `run_analytics_query` | natural_language_question | Text-to-SQL fallback for complex questions. Generates and executes a read-only SQL query with strict safeguards (read-only DB role, 5s timeout, 1000 row limit). |

---

## 5. Receipt Parsing Pipeline

### 5.1 Flow

1. User sends a photo in the Telegram chat
2. Bot downloads the image via Telegram API
3. Image is sent to GPT-4o Vision with a structured extraction prompt
4. GPT-4o returns structured JSON: store name, date, item list (name, qty, unit price, total, discount), subtotal, tax, total
5. Bot validates extracted data against the JSON schema (Pydantic)
6. Items are fuzzy-matched against canonical products (>80% confidence = auto-link, otherwise ask user or create new product)
7. Receipt and items are stored in the database
8. Bot sends a formatted summary to the user for confirmation
9. User confirms or provides corrections
10. Receipt is finalized

### 5.2 Vision Model Prompt Strategy

The prompt instructs GPT-4o to:
- Extract all visible text from the receipt image
- Identify store name and address
- Parse the date in ISO format
- List every line item with: name as printed, quantity, unit price, total price, any discount notation
- Identify subtotal, tax amounts, and final total
- Return the result as a strict JSON object matching the defined Pydantic schema
- Flag any fields it could not confidently extract

---

## 6. Technology Stack

### 6.1 Language and Runtime

- **Python 3.12+** with full type annotations
- **asyncio** for concurrent I/O operations
- **Pydantic 2.x** for data validation throughout

### 6.2 Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| aiogram | ^3.x | Async Telegram bot framework |
| litellm | ^1.x | Unified LLM API (Gemini, OpenAI, Anthropic, local) |
| sqlalchemy | ^2.x | Async ORM with type-safe models |
| alembic | ^1.x | Database schema migrations |
| asyncpg | ^0.29 | Async PostgreSQL driver |
| pydantic | ^2.x | Data validation and settings management |
| pydantic-settings | ^2.x | Environment-based configuration |
| pillow | ^10.x | Image preprocessing |
| rapidfuzz | ^3.x | Fuzzy string matching for product reconciliation |

### 6.3 Development Dependencies

| Package | Purpose |
|---------|---------|
| pytest | Testing framework |
| pytest-asyncio | Async test support |
| ruff | Linting and formatting |
| mypy | Static type checking |

### 6.4 Database

- **PostgreSQL 16** in a Docker container
- Features used: JSONB, full-text search (tsvector), window functions, CTEs, array types

### 6.5 Infrastructure

- **Docker** + **Docker Compose** for containerization
- **Caddy** as reverse proxy (automatic HTTPS, minimal config)
- **GitHub Actions** for CI/CD
- **Hetzner Cloud CX22** VPS for production deployment

---

## 7. Security

- **Authentication**: Telegram user ID verification. Auto-registration on first `/start`. Telegram handles identity.
- **Database access**: Application uses parameterized queries via SQLAlchemy. The `run_analytics_query` tool uses a separate read-only PostgreSQL role with query timeout (5s) and row limit (1000).
- **Rate limiting**: Per-user rate limits on message processing and API calls to prevent abuse and cost overruns.
- **Secrets**: All API keys and credentials stored in environment variables. `.env.example` provided with placeholder values. Never committed to the repository.
- **Input validation**: All tool inputs validated with Pydantic schemas before execution. Invalid inputs return clear error messages.
- **Image handling**: Receipt images processed in-memory. Optionally persisted to a Docker volume for reference.

---

## 8. System Prompt Design

The agent's system prompt defines its behavior:

- **Role**: Personal purchase and shopping assistant
- **Scope**: ONLY handles purchase, receipt, shopping list, and spending analytics topics. Politely declines off-topic requests.
- **Data integrity**: Always uses tools to answer data questions. Never guesses or fabricates purchase data.
- **Response style**: Concise and friendly. Consistent monetary formatting. Uses lists/tables for multi-item results.
- **Context injection**: User information (ID, timezone, currency preference) injected per-request for personalized responses.

---

## 9. Cost Estimate (Monthly)

| Item | Estimated Cost |
|------|---------------|
| Hetzner CX22 VPS | ~4.50 EUR |
| Gemini Flash API (conversational) | ~0.50-2.00 EUR |
| GPT-4o API (receipt vision) | ~0.50-1.00 EUR |
| Domain (optional) | ~1.00 EUR amortized |
| **Total** | **~6-9 EUR/month** |

---

## 10. Development Phases

| Phase | Scope | Timeline |
|-------|-------|----------|
| 1. Foundation | Project scaffolding, Docker Compose, PostgreSQL, DB schema, Alembic migrations, basic Telegram bot | Week 1-2 |
| 2. Agent Core | LLM integration via LiteLLM, agent loop, core tools (search, spending, manual entry), system prompt | Week 2-3 |
| 3. Receipt Parsing | Vision model integration (GPT-4o), receipt photo handling, structured extraction, product matching, confirmation flow | Week 3-4 |
| 4. Full Features | Shopping lists, discount tracking, advanced analytics, text-to-SQL, price comparison | Week 4-5 |
| 5. Polish & Deploy | CI/CD, VPS deployment, testing suite, documentation, error handling | Week 5-6 |

---

## 11. Future Extensibility

- Web dashboard (FastAPI + frontend)
- WhatsApp or other messaging platform integration
- Scheduled spending reports and budget alerts
- Price trend analysis and notifications
- Store loyalty program integration
- Multi-currency support
- Export to CSV/PDF
