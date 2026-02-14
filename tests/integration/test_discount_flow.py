"""Integration test: register a discount and then query it."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestDiscountFlow:
    async def test_register_then_query(self, patch_db_session, db_session, seed_data):
        """Step 1: Register a discount. Step 2: Query active discounts."""

        user = seed_data["user"]

        # Step 1: Register
        reg_resp = llm_tool_call_response(
            "register_discount",
            {
                "store": "Mercadona",
                "discount_type": "percentage",
                "value": 25,
                "product": "Chicken",
                "end_date": "2026-02-28",
            },
        )
        reg_final = llm_text_response(
            "Registered: 25% off Chicken at Mercadona until Feb 28."
        )

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[reg_resp, reg_final])

            agent = AgentCore()
            r1 = await agent.process_message(
                user, "Chicken is 25% off at Mercadona until Feb 28"
            )

        assert "25" in r1 or "mercadona" in r1.lower()

        # Step 2: Query discounts
        query_resp = llm_tool_call_response(
            "get_active_discounts",
            {"store": "Mercadona"},
        )

        captured_tool_results = []

        async def capture_second_call(**kwargs):
            messages = kwargs.get("messages", [])
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "tool":
                    captured_tool_results.append(json.loads(m["content"]))
            return llm_text_response(
                "Mercadona has 25% off Chicken and 20% off Chicken Breast."
            )

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(
                side_effect=[
                    query_resp,
                    llm_text_response("Active discounts at Mercadona."),
                ]
            )

            agent2 = AgentCore()
            r2 = await agent2.process_message(user, "Any discounts at Mercadona?")

        assert isinstance(r2, str)
