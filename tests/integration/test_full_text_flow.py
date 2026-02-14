"""Integration test: full text message flow from user query to DB query to response."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestFullTextFlow:
    async def test_user_asks_spending_at_mercadona(
        self, patch_db_session, db_session, seed_data
    ):
        """Full flow: user asks 'How much at Mercadona this month?' ->
        agent calls get_spending_summary -> real DB query -> LLM formats response."""

        user = seed_data["user"]

        # Round 1: LLM decides to call get_spending_summary
        tool_response = llm_tool_call_response(
            "get_spending_summary",
            {"store": "Mercadona", "period": "last_3_months"},
        )
        # Round 2: LLM returns formatted text with the result
        final_response = llm_text_response(
            "You've spent some money at Mercadona recently."
        )

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(
                side_effect=[tool_response, final_response]
            )

            agent = AgentCore()
            result = await agent.process_message(
                user=user,
                message_text="How much did I spend at Mercadona this month?",
            )

        # The agent returned a string response
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify the tool was actually called (not just mocked through)
        assert mock_litellm.acompletion.call_count == 2

        # Verify the second call included the tool result
        second_call = mock_litellm.acompletion.call_args_list[1]
        messages = second_call.kwargs.get("messages", [])
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1

        # The tool result should contain real data from the DB
        tool_result = json.loads(tool_messages[0]["content"])
        assert "total_spent" in tool_result
        assert tool_result["total_spent"] > 0  # Seed data has Mercadona purchases
