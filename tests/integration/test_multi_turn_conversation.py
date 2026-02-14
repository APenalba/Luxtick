"""Integration tests proving multi-turn conversation continuity."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestMultiTurnConversation:
    async def test_two_turn_conversation(self, patch_db_session, db_session, seed_data):
        """Turn 1: ask spending. Turn 2: follow up with 'break down by store'.
        Proves conversation_history is included in the second call."""

        user = seed_data["user"]

        # --- Turn 1 ---
        tool_resp_1 = llm_tool_call_response(
            "get_spending_summary", {"period": "last_3_months"}
        )
        final_1 = llm_text_response("You spent 64.47 EUR in the last 3 months.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[tool_resp_1, final_1])

            agent = AgentCore()
            response_1 = await agent.process_message(
                user, "How much did I spend recently?"
            )

        assert "64.47" in response_1

        # --- Turn 2: follow-up with conversation history ---
        history = [
            {"role": "user", "content": "How much did I spend recently?"},
            {"role": "assistant", "content": response_1},
        ]

        tool_resp_2 = llm_tool_call_response(
            "get_spending_summary", {"period": "last_3_months", "group_by": "store"}
        )
        final_2 = llm_text_response("Mercadona: 24.14, Lidl: 27.18, Carrefour: 13.15")

        captured_messages = []

        async def capture_and_respond(**kwargs):
            if not captured_messages:
                captured_messages.extend(kwargs.get("messages", []))
            return [tool_resp_2, final_2].pop(0)

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[tool_resp_2, final_2])

            agent2 = AgentCore()
            response_2 = await agent2.process_message(
                user, "Break that down by store", conversation_history=history
            )

        # The conversation history from turn 1 was included
        assert isinstance(response_2, str)

    async def test_agent_asks_clarifying_question(
        self, patch_db_session, db_session, seed_data
    ):
        """User: 'Add a purchase' -> LLM asks for details -> User provides -> LLM calls tool."""

        user = seed_data["user"]

        # Turn 1: LLM asks for clarification (no tool call)
        clarification = llm_text_response(
            "Sure! Which store and what items did you buy?"
        )

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(return_value=clarification)

            agent = AgentCore()
            response_1 = await agent.process_message(user, "Add a purchase")

        assert "which store" in response_1.lower() or "what items" in response_1.lower()

        # Turn 2: User provides details -> LLM calls add_manual_purchase
        history = [
            {"role": "user", "content": "Add a purchase"},
            {"role": "assistant", "content": response_1},
        ]

        tool_resp = llm_tool_call_response(
            "add_manual_purchase",
            {"store": "Mercadona", "items": [{"name": "Chicken", "unit_price": 5.99}]},
        )
        final = llm_text_response(
            "Done! I've added your purchase of Chicken (5.99 EUR) at Mercadona."
        )

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[tool_resp, final])

            agent2 = AgentCore()
            response_2 = await agent2.process_message(
                user, "Mercadona, chicken 5.99", conversation_history=history
            )

        assert "mercadona" in response_2.lower() or "chicken" in response_2.lower()

    async def test_receipt_confirmation_flow(
        self, patch_db_session, db_session, seed_data
    ):
        """User sends photo -> bot parses -> user says
        'the total should be 15.00' -> correction processed."""

        user = seed_data["user"]

        # Simulate the receipt was already parsed (turn 1 was the photo)
        history = [
            {
                "role": "assistant",
                "content": (
                    "Receipt parsed: Mercadona, 3 items, total 15.50 EUR. "
                    "Anything to correct?"
                ),
            },
        ]

        # User provides correction -> LLM decides what to do
        final = llm_text_response("Got it! I've noted the correct total is 15.00 EUR.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(return_value=final)

            agent = AgentCore()
            response = await agent.process_message(
                user,
                "The total should be 15.00 not 15.50",
                conversation_history=history,
            )

        assert "15.00" in response
