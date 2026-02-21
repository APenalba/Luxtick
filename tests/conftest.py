"""Shared test fixtures for the entire test suite."""

import json
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base, User

# ---------------------------------------------------------------------------
# Environment setup for tests (must happen before importing settings)
# ---------------------------------------------------------------------------
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://bot:your_very_secure_password_here@localhost:5433/luxtick_test",
)
os.environ.setdefault(
    "DATABASE_URL_READONLY",
    "postgresql+asyncpg://bot_readonly:readonly_password@localhost:5433/luxtick_test",
)

# ---------------------------------------------------------------------------
# Database fixtures (real PostgreSQL for service/integration/db tests)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
async def db_engine():
    """Create a test database engine (per-test to avoid event-loop conflicts)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session wrapped in a transaction that rolls back after the test."""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False
        )
        session = session_factory()
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
def patch_db_session(db_session):
    """Patch `async_session` in all modules that import it to use the test session."""

    class FakeSessionCtx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            # Don't commit — the outer transaction will rollback
            pass

    factory = lambda: FakeSessionCtx()  # noqa: E731

    # Patch async_session at every import location
    modules_using_async_session = [
        "src.db.session",
        "src.services.purchase",
        "src.services.analytics",
        "src.services.shopping_list",
        "src.services.discount",
        "src.services.product",
        "src.agent.receipt_parser",
        "src.bot.middlewares.auth",
    ]
    patches = []
    for module in modules_using_async_session:
        p = patch(f"{module}.async_session", side_effect=factory)
        patches.append(p)
        p.start()
    try:
        yield db_session
    finally:
        for p in patches:
            p.stop()


@pytest.fixture
def patch_readonly_session(db_session):
    """Patch `readonly_session` in all modules that import it to use the test session."""

    class FakeSessionCtx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            pass

    factory = lambda: FakeSessionCtx()  # noqa: E731

    modules_using_readonly_session = [
        "src.db.session",
        "src.services.text_to_sql",
    ]
    patches = []
    for module in modules_using_readonly_session:
        p = patch(f"{module}.readonly_session", side_effect=factory)
        patches.append(p)
        p.start()
    try:
        yield db_session
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Sample ORM objects (in-memory, no DB needed)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_user() -> User:
    """An in-memory User instance for unit tests (not persisted)."""
    return User(
        id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        telegram_id=111222333,
        username="testuser",
        first_name="Test",
        language="en",
        currency="EUR",
        timezone="UTC",
        preferences={},
    )


@pytest.fixture
async def db_user(db_session: AsyncSession) -> User:
    """A User persisted in the test database."""
    user = User(
        id=uuid.uuid4(),
        telegram_id=111222333,
        username="testuser",
        first_name="Test",
        language="en",
        currency="EUR",
        timezone="UTC",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def seed_data(db_session: AsyncSession) -> dict:
    """Fixture that populates the test DB with realistic seed data."""
    from tests.factories import seed_test_data

    return await seed_test_data(db_session)


# ---------------------------------------------------------------------------
# LLM mock response builders
# ---------------------------------------------------------------------------


def llm_text_response(content: str) -> MagicMock:
    """Build a mock LiteLLM response with plain text (no tool calls)."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    message.model_dump.return_value = {"role": "assistant", "content": content}

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def llm_tool_call_response(
    tool_name: str, arguments: dict, tool_call_id: str = "call_001"
) -> MagicMock:
    """Build a mock LiteLLM response that triggers one tool call."""
    tool_call = MagicMock()
    tool_call.id = tool_call_id
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(arguments)

    message = MagicMock()
    message.content = None
    message.tool_calls = [tool_call]
    message.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tool_call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments)},
            }
        ],
    }

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Telegram mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bot():
    """A mock aiogram Bot."""
    bot = AsyncMock()
    bot.get_file = AsyncMock()
    bot.download_file = AsyncMock()
    return bot


def make_mock_message(
    text: str | None = "Hello",
    from_user_id: int = 111222333,
    from_username: str = "testuser",
    from_first_name: str = "Test",
    photo: list | None = None,
) -> MagicMock:
    """Factory to create a mock aiogram Message."""
    msg = AsyncMock()
    msg.text = text
    msg.photo = photo

    msg.from_user = MagicMock()
    msg.from_user.id = from_user_id
    msg.from_user.username = from_username
    msg.from_user.first_name = from_first_name

    msg.chat = AsyncMock()
    msg.chat.do = AsyncMock()

    msg.answer = AsyncMock()
    msg.bot = AsyncMock()
    msg.bot.get_file = AsyncMock()
    msg.bot.download_file = AsyncMock()
    return msg


def make_mock_callback(data: str | None = "receipt_confirm:abc123") -> MagicMock:
    """Factory to create a mock aiogram CallbackQuery."""
    cb = AsyncMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = 111222333
    cb.from_user.username = "testuser"
    cb.from_user.first_name = "Test"
    cb.answer = AsyncMock()
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    return cb


# ---------------------------------------------------------------------------
# Settings override
# ---------------------------------------------------------------------------


@pytest.fixture
def override_settings():
    """Context manager that patches settings attributes."""
    from src.config import settings

    original_values: dict[str, Any] = {}

    def _override(**kwargs):
        for key, value in kwargs.items():
            original_values[key] = getattr(settings, key)
            object.__setattr__(settings, key, value)

    yield _override

    for key, value in original_values.items():
        object.__setattr__(settings, key, value)
