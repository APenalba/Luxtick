# Contributing to LuxTick

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- API keys for Gemini and OpenAI (see [.env.example](.env.example))

### Getting Started

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/chatbot.git
   cd chatbot
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies (including dev tools):**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up your environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Start the development database:**
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

6. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

7. **Start the bot (polling mode):**
   ```bash
   python -m src.main
   ```

## Code Quality

We use the following tools to maintain code quality:

- **ruff** for linting and formatting
- **mypy** for static type checking
- **pytest** for testing

### Running Checks

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/ --ignore-missing-imports

# Tests
pytest tests/ -v
```

## Project Structure

- `src/bot/` -- Telegram bot handlers and middlewares (aiogram)
- `src/agent/` -- LLM agent core, tool definitions, prompts
- `src/db/` -- Database models and session management
- `src/services/` -- Business logic layer
- `tests/` -- Test suite
- `alembic/` -- Database migrations

## Making Changes

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes, following existing code patterns.

3. Add tests for new functionality.

4. Ensure all checks pass:
   ```bash
   ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ --ignore-missing-imports && pytest tests/ -v
   ```

5. Commit with a clear message and open a pull request.

## Adding a New Tool

To add a new capability for the bot:

1. Define the tool schema in `src/agent/tools.py` (follows OpenAI function-calling format)
2. Create or update the relevant service in `src/services/`
3. Add the handler method in `src/agent/tool_executor.py`
4. Update the system prompt in `src/agent/prompts.py` if needed
5. Add tests

## Database Migrations

When changing models in `src/db/models.py`:

```bash
# Auto-generate a migration
alembic revision --autogenerate -m "Description of change"

# Review the generated migration in alembic/versions/
# Then apply it:
alembic upgrade head
```

## Questions?

Open an issue if you have questions or need help getting started.
