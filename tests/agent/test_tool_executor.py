"""Tests for the ToolExecutor dispatch logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.tool_executor import ToolExecutor
from src.agent.tools import TOOL_DEFINITIONS

pytestmark = [pytest.mark.agent, pytest.mark.asyncio]


class TestToolExecutor:
    @pytest.fixture
    def executor(self):
        ex = ToolExecutor()
        # Use AsyncMock so any method access is awaitable
        ex.purchase_service = AsyncMock()
        ex.analytics_service = AsyncMock()
        ex.shopping_list_service = AsyncMock()
        ex.discount_service = AsyncMock()
        return ex

    async def test_dispatch_search_purchases(self, executor, sample_user):
        executor.purchase_service.search_purchases = AsyncMock(
            return_value={"results": []}
        )
        await executor.execute("search_purchases", {"query": "chicken"}, sample_user)
        executor.purchase_service.search_purchases.assert_called_once()

    async def test_dispatch_get_spending_summary(self, executor, sample_user):
        executor.analytics_service.get_spending_summary = AsyncMock(return_value={})
        await executor.execute(
            "get_spending_summary", {"period": "this_month"}, sample_user
        )
        executor.analytics_service.get_spending_summary.assert_called_once()

    async def test_dispatch_add_manual_purchase(self, executor, sample_user):
        executor.purchase_service.add_manual_purchase = AsyncMock(return_value={})
        await executor.execute(
            "add_manual_purchase",
            {"store": "Mercadona", "items": [{"name": "X", "unit_price": 1}]},
            sample_user,
        )
        executor.purchase_service.add_manual_purchase.assert_called_once()

    async def test_dispatch_create_shopping_list(self, executor, sample_user):
        executor.shopping_list_service.create_list = AsyncMock(return_value={})
        await executor.execute("create_shopping_list", {"name": "Weekend"}, sample_user)
        executor.shopping_list_service.create_list.assert_called_once()

    async def test_dispatch_update_shopping_list(self, executor, sample_user):
        executor.shopping_list_service.update_list = AsyncMock(return_value={})
        await executor.execute(
            "update_shopping_list", {"list_name": "Weekend"}, sample_user
        )
        executor.shopping_list_service.update_list.assert_called_once()

    async def test_dispatch_register_discount(self, executor, sample_user):
        executor.discount_service.register_discount = AsyncMock(return_value={})
        await executor.execute(
            "register_discount",
            {"store": "Mercadona", "discount_type": "percentage", "value": 20},
            sample_user,
        )
        executor.discount_service.register_discount.assert_called_once()

    async def test_dispatch_run_analytics_query(self, executor, sample_user):
        with patch("src.services.text_to_sql.TextToSQLService") as mock_tts:
            mock_svc = MagicMock()
            mock_svc.execute_query = AsyncMock(return_value={"status": "success"})
            mock_tts.return_value = mock_svc

            await executor.execute(
                "run_analytics_query",
                {
                    "question": "how many stores?",
                    "sql_query": "SELECT COUNT(*) FROM stores",
                },
                sample_user,
            )
            mock_svc.execute_query.assert_called_once()

    async def test_dispatch_all_13_tools(self, executor, sample_user):
        """Every tool name in TOOL_DEFINITIONS resolves without ValueError."""
        tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        for name in tool_names:
            if name == "run_analytics_query":
                with patch("src.services.text_to_sql.TextToSQLService") as mock_tts:
                    mock_svc = MagicMock()
                    mock_svc.execute_query = AsyncMock(return_value={})
                    mock_tts.return_value = mock_svc
                    await executor.execute(
                        name, {"question": "q", "sql_query": "SELECT 1"}, sample_user
                    )
            else:
                # Provide minimal required args; services are AsyncMock so any method is awaitable
                import contextlib

                with contextlib.suppress(TypeError):
                    await executor.execute(name, {}, sample_user)

    async def test_unknown_tool_raises_valueerror(self, executor, sample_user):
        with pytest.raises(ValueError, match="Unknown tool"):
            await executor.execute("nonexistent_tool", {}, sample_user)

    async def test_optional_args_default_correctly(self, executor, sample_user):
        executor.purchase_service.search_purchases = AsyncMock(return_value={})
        await executor.execute("search_purchases", {}, sample_user)
        call_kwargs = executor.purchase_service.search_purchases.call_args.kwargs
        assert call_kwargs.get("limit") == 20
