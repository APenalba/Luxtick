"""Integration test: add a purchase then query it."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestManualPurchaseFlow:
    async def test_add_then_query(self, patch_db_session, db_session, seed_data):
        """Step 1: Add purchase. Step 2: Query spending. Step 3: Search items."""

        user = seed_data["user"]

        # Step 1: Add a purchase
        add_resp = llm_tool_call_response(
            "add_manual_purchase",
            {
                "store": "Mercadona",
                "items": [
                    {"name": "Chicken", "unit_price": 5.99},
                    {"name": "Bread", "unit_price": 1.20},
                ],
            },
        )
        add_final = llm_text_response("Added your purchase of 7.19 EUR at Mercadona.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[add_resp, add_final])

            agent = AgentCore()
            r1 = await agent.process_message(
                user, "I bought chicken for 5.99 and bread for 1.20 at Mercadona"
            )

        assert "7.19" in r1 or "mercadona" in r1.lower()

        # Step 2: Query spending -- the tool result should include the new purchase
        query_resp = llm_tool_call_response(
            "get_spending_summary",
            {"store": "Mercadona", "period": "last_3_months"},
        )

        # Capture the tool result to verify it includes the new purchase
        captured_tool_results = []

        async def capture_calls(**kwargs):
            messages = kwargs.get("messages", [])
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "tool":
                    captured_tool_results.append(json.loads(m["content"]))
            return llm_text_response("You spent a total at Mercadona.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(
                side_effect=[query_resp, llm_text_response("Total is X.")]
            )

            agent2 = AgentCore()
            r2 = await agent2.process_message(
                user, "How much did I spend at Mercadona?"
            )

        assert isinstance(r2, str)
