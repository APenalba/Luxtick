"""Integration test: full shopping list lifecycle through the agent."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestShoppingListLifecycle:
    async def test_create_add_show_check(self, patch_db_session, db_session, seed_data):
        """Step 1: Create list. Step 2: Add items. Step 3: Show. Step 4: Check items."""

        user = seed_data["user"]

        async def run_turn(message, tool_name, tool_args, llm_reply, history=None):
            tool_resp = llm_tool_call_response(tool_name, tool_args)
            final = llm_text_response(llm_reply)

            with (
                patch("src.agent.core.litellm") as mock_litellm,
                patch("src.agent.core.settings") as mock_settings,
            ):
                mock_settings.gemini_api_key = "test"
                mock_settings.openai_api_key = "test"
                mock_settings.conversational_model = "test-model"
                mock_litellm.acompletion = AsyncMock(side_effect=[tool_resp, final])

                agent = AgentCore()
                return await agent.process_message(
                    user, message, conversation_history=history
                )

        # Step 1: Create
        r1 = await run_turn(
            "Create a shopping list for the weekend with milk, eggs, and bread",
            "create_shopping_list",
            {
                "name": "Weekend",
                "items": [{"name": "Milk"}, {"name": "Eggs"}, {"name": "Bread"}],
            },
            "Created 'Weekend' list with 3 items!",
        )
        assert "Weekend" in r1 or "3" in r1

        # Step 2: Add items
        r2 = await run_turn(
            "Add chicken and rice to my list",
            "update_shopping_list",
            {
                "list_name": "Weekend",
                "add_items": [{"name": "Chicken"}, {"name": "Rice"}],
            },
            "Added chicken and rice to your Weekend list!",
        )
        assert "chicken" in r2.lower() or "rice" in r2.lower()

        # Step 3: Show lists
        show_resp = llm_tool_call_response("get_shopping_lists", {"active_only": True})
        show_final = llm_text_response("Your Weekend list has 5 items.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[show_resp, show_final])

            agent = AgentCore()
            r3 = await agent.process_message(user, "Show my shopping lists")

        assert isinstance(r3, str)

        # Step 4: Check items
        r4 = await run_turn(
            "I bought the milk and eggs",
            "update_shopping_list",
            {"list_name": "Weekend", "check_items": ["Milk", "Eggs"]},
            "Checked off milk and eggs from your Weekend list!",
        )
        assert "milk" in r4.lower() or "eggs" in r4.lower() or "checked" in r4.lower()
