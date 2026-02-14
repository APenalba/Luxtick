"""Tool executor: dispatches tool calls from the LLM to the appropriate service functions."""

import logging
from typing import Any

from src.db.models import User
from src.services.analytics import AnalyticsService
from src.services.discount import DiscountService
from src.services.purchase import PurchaseService
from src.services.shopping_list import ShoppingListService

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tool calls by dispatching to the appropriate service layer."""

    def __init__(self) -> None:
        self.purchase_service = PurchaseService()
        self.analytics_service = AnalyticsService()
        self.shopping_list_service = ShoppingListService()
        self.discount_service = DiscountService()

        # Map tool names to handler methods
        self._handlers: dict[str, Any] = {
            "search_purchases": self._search_purchases,
            "get_spending_summary": self._get_spending_summary,
            "get_frequent_purchases": self._get_frequent_purchases,
            "compare_prices": self._compare_prices,
            "get_product_history": self._get_product_history,
            "get_active_discounts": self._get_active_discounts,
            "add_manual_purchase": self._add_manual_purchase,
            "register_discount": self._register_discount,
            "create_shopping_list": self._create_shopping_list,
            "update_shopping_list": self._update_shopping_list,
            "get_shopping_lists": self._get_shopping_lists,
            "suggest_shopping_list": self._suggest_shopping_list,
            "run_analytics_query": self._run_analytics_query,
        }

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user: User,
    ) -> Any:
        """Execute a tool call and return the result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments passed by the LLM.
            user: The current user (for data scoping).

        Returns:
            The tool result (will be serialized to JSON for the LLM).

        Raises:
            ValueError: If the tool name is not recognized.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return await handler(user=user, **arguments)

    # -------------------------------------------------------------------------
    # DATA RETRIEVAL
    # -------------------------------------------------------------------------

    async def _search_purchases(
        self,
        user: User,
        query: str | None = None,
        store: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await self.purchase_service.search_purchases(
            user_id=user.id,
            query=query,
            store=store,
            category=category,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def _get_spending_summary(
        self,
        user: User,
        period: str | None = None,
        group_by: str | None = None,
        store: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        return await self.analytics_service.get_spending_summary(
            user_id=user.id,
            period=period,
            group_by=group_by,
            store=store,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )

    async def _get_frequent_purchases(
        self,
        user: User,
        period: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return await self.analytics_service.get_frequent_purchases(
            user_id=user.id,
            period=period,
            limit=limit,
        )

    async def _compare_prices(
        self,
        user: User,
        product: str,
        store: str | None = None,
        period: str | None = None,
    ) -> dict[str, Any]:
        return await self.analytics_service.compare_prices(
            user_id=user.id,
            product=product,
            store=store,
            period=period,
        )

    async def _get_product_history(
        self,
        user: User,
        product: str,
    ) -> dict[str, Any]:
        return await self.purchase_service.get_product_history(
            user_id=user.id,
            product=product,
        )

    async def _get_active_discounts(
        self,
        user: User,
        store: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        return await self.discount_service.get_active_discounts(
            store=store,
            category=category,
        )

    # -------------------------------------------------------------------------
    # DATA ENTRY
    # -------------------------------------------------------------------------

    async def _add_manual_purchase(
        self,
        user: User,
        store: str,
        items: list[dict[str, Any]],
        date: str | None = None,
        total: float | None = None,
    ) -> dict[str, Any]:
        return await self.purchase_service.add_manual_purchase(
            user_id=user.id,
            store_name=store,
            items=items,
            purchase_date=date,
            total_amount=total,
        )

    async def _register_discount(
        self,
        user: User,
        store: str,
        discount_type: str,
        value: float,
        product: str | None = None,
        description: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        return await self.discount_service.register_discount(
            store_name=store,
            product_name=product,
            discount_type=discount_type,
            value=value,
            description=description,
            start_date=start_date,
            end_date=end_date,
        )

    # -------------------------------------------------------------------------
    # SHOPPING LISTS
    # -------------------------------------------------------------------------

    async def _create_shopping_list(
        self,
        user: User,
        name: str,
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await self.shopping_list_service.create_list(
            user_id=user.id,
            name=name,
            items=items or [],
        )

    async def _update_shopping_list(
        self,
        user: User,
        list_name: str,
        add_items: list[dict[str, Any]] | None = None,
        remove_items: list[str] | None = None,
        check_items: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self.shopping_list_service.update_list(
            user_id=user.id,
            list_name=list_name,
            add_items=add_items,
            remove_items=remove_items,
            check_items=check_items,
        )

    async def _get_shopping_lists(
        self,
        user: User,
        active_only: bool = True,
    ) -> dict[str, Any]:
        return await self.shopping_list_service.get_lists(
            user_id=user.id,
            active_only=active_only,
        )

    async def _suggest_shopping_list(
        self,
        user: User,
        based_on: str | None = None,
    ) -> dict[str, Any]:
        return await self.shopping_list_service.suggest_list(
            user_id=user.id,
            based_on=based_on or "weekly_habits",
        )

    # -------------------------------------------------------------------------
    # ADVANCED ANALYTICS
    # -------------------------------------------------------------------------

    async def _run_analytics_query(
        self,
        user: User,
        question: str,
        sql_query: str,
    ) -> dict[str, Any]:
        from src.services.text_to_sql import TextToSQLService

        service = TextToSQLService()
        return await service.execute_query(
            user_id=user.id,
            question=question,
            sql_query=sql_query,
        )
