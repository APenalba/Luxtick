# LuxTick

An intelligent Telegram bot that acts as your personal purchase, receipt, and shopping list manager. Powered by LLM tool-calling for natural language understanding -- no rigid commands or intents needed.

Ask it anything about your spending: *"How much have I spent on chicken this month?"*, *"What do I usually buy weekly?"*, or simply send a photo of your receipt and it will extract everything automatically.

## Features

- **Natural Language Queries** -- Ask free-form questions about your spending habits, purchase history, and shopping patterns
- **Receipt Photo Parsing** -- Upload a receipt photo and the bot extracts all items, prices, store info, and discounts via GPT-4o vision
- **Shopping List Management** -- Create, update, and get AI-suggested shopping lists based on your purchase patterns
- **Spending Analytics** -- Breakdowns by store, category, product, and time period
- **Discount Tracking** -- Register and query active offers and promotions
- **Manual Data Entry** -- Add purchases conversationally

## Architecture

```
Telegram <-> Caddy (reverse proxy) <-> Bot (Python/aiogram) <-> LLM (Gemini Flash / GPT-4o)
                                                |
                                           PostgreSQL
```

The bot uses an **LLM agent with tool-calling** pattern:

1. You send a message or photo via Telegram
2. The bot forwards it to Gemini 2.0 Flash along with available tool definitions
3. The LLM decides which tool(s) to call (e.g., `get_spending_summary`, `search_purchases`)
4. The bot executes the tool against PostgreSQL and returns results to the LLM
5. The LLM formats a natural language response and sends it back to you

For receipt photos, GPT-4o vision extracts structured data from the image, then the system fuzzy-matches items to canonical products in the database.

See [SPECS.md](SPECS.md) for the full technical specification.

## Tech Stack

- **Python 3.12+** with asyncio
- **aiogram 3.x** -- Async Telegram bot framework
- **LiteLLM** -- Unified LLM API (Gemini, OpenAI, Anthropic)
- **SQLAlchemy 2.x** -- Async ORM
- **PostgreSQL 16** -- Relational database
- **Alembic** -- Database migrations
- **Docker Compose** -- Containerized deployment
- **Caddy** -- Reverse proxy with automatic HTTPS
- **GitHub Actions** -- CI/CD pipeline

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Google AI API key (for Gemini Flash) -- [Get one here](https://aistudio.google.com/apikey)
- An OpenAI API key (for receipt vision) -- [Get one here](https://platform.openai.com/api-keys)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/chatbot.git
   cd chatbot
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and settings
   ```

3. **Start the services**:
   ```bash
   docker compose up -d
   ```

4. **Run database migrations**:
   ```bash
   docker compose exec bot alembic upgrade head
   ```

5. **Talk to your bot** on Telegram!

### Local Development

```bash
# Start only the database
docker compose -f docker-compose.dev.yml up -d

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start the bot
python -m src.main
```

## Project Structure

```
chatbot/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Settings from environment
│   ├── bot/                 # Telegram bot (aiogram handlers, middlewares)
│   ├── agent/               # LLM agent (core loop, tools, prompts)
│   ├── db/                  # Database models and session management
│   └── services/            # Business logic layer
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── docker-compose.yml       # Production deployment
├── docker-compose.dev.yml   # Local development
├── Dockerfile
├── SPECS.md                 # Full technical specification
└── .env.example             # Environment variable template
```

## Configuration

All configuration is done via environment variables. See [.env.example](.env.example) for the full list.

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather | Yes |
| `GEMINI_API_KEY` | Google AI API key for Gemini Flash | Yes |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o vision | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `BOT_WEBHOOK_URL` | Public URL for Telegram webhook | Production only |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
