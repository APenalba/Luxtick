"""Agent core loop tests with mocked LLM."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.core import AgentCore
from tests.conftest import llm_text_response, llm_tool_call_response

pytestmark = [pytest.mark.agent, pytest.mark.asyncio]


class TestAgentCore:
    async def test_simple_text_response(self, sample_user):
        """LLM returns plain text -> that text is returned to user."""
        mock_response = llm_text_response("You spent 50 EUR this month.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(return_value=mock_response)

            agent = AgentCore()
            result = await agent.process_message(sample_user, "How much did I spend?")

        assert result == "You spent 50 EUR this month."

    async def test_single_tool_call_and_response(self, sample_user):
        """LLM calls a tool, then returns final text."""
        tool_response = llm_tool_call_response(
            "get_spending_summary",
            {"period": "this_month"},
        )
        final_response = llm_text_response(
            "You spent 127.45 EUR this month at Mercadona."
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
            agent.tool_executor = MagicMock()
            agent.tool_executor.execute = AsyncMock(
                return_value={"total_spent": 127.45}
            )

            result = await agent.process_message(sample_user, "How much this month?")

        assert "127.45" in result
        agent.tool_executor.execute.assert_called_once()

    async def test_multiple_tool_calls_in_sequence(self, sample_user):
        """LLM calls tool A in round 1, tool B in round 2, then final text."""
        round1 = llm_tool_call_response(
            "search_purchases", {"query": "chicken"}, "call_1"
        )
        round2 = llm_tool_call_response(
            "get_spending_summary", {"period": "this_month"}, "call_2"
        )
        final = llm_text_response("Here's your summary.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[round1, round2, final])

            agent = AgentCore()
            agent.tool_executor = MagicMock()
            agent.tool_executor.execute = AsyncMock(return_value={"results": []})

            _ = await agent.process_message(sample_user, "Complex query")

        assert agent.tool_executor.execute.call_count == 2

    async def test_max_rounds_produces_final_response(self, sample_user):
        """After MAX_TOOL_ROUNDS, the agent forces a final answer."""
        # 5 rounds of tool calls, then a forced final
        tool_responses = [
            llm_tool_call_response("search_purchases", {}, f"call_{i}")
            for i in range(5)
        ]
        final = llm_text_response("Here's what I found.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[*tool_responses, final])

            agent = AgentCore()
            agent.tool_executor = MagicMock()
            agent.tool_executor.execute = AsyncMock(return_value={})

            result = await agent.process_message(sample_user, "Keep calling tools")

        assert result == "Here's what I found."

    async def test_llm_api_failure_returns_error_message(self, sample_user):
        """LLM raises exception -> user gets friendly error."""
        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=Exception("API down"))

            agent = AgentCore()
            result = await agent.process_message(sample_user, "Hello")

        assert "trouble" in result.lower() or "sorry" in result.lower()

    async def test_tool_execution_failure_continues(self, sample_user):
        """Tool raises exception -> error sent as tool result -> LLM handles gracefully."""
        tool_response = llm_tool_call_response("search_purchases", {})
        final = llm_text_response("Sorry, I couldn't find that data.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[tool_response, final])

            agent = AgentCore()
            agent.tool_executor = MagicMock()
            agent.tool_executor.execute = AsyncMock(side_effect=Exception("DB error"))

            result = await agent.process_message(sample_user, "Search something")

        # Should not crash, should return LLM's response
        assert isinstance(result, str)

    async def test_invalid_tool_arguments_handled(self, sample_user):
        """LLM sends malformed JSON args -> empty dict used, no crash."""
        # Create a tool call with invalid JSON
        tool_call = MagicMock()
        tool_call.id = "call_001"
        tool_call.function.name = "search_purchases"
        tool_call.function.arguments = "not valid json {{"

        message = MagicMock()
        message.content = None
        message.tool_calls = [tool_call]
        message.model_dump.return_value = {
            "role": "assistant",
            "content": None,
            "tool_calls": [],
        }

        choice = MagicMock()
        choice.message = message
        round1 = MagicMock()
        round1.choices = [choice]

        final = llm_text_response("Here's the result.")

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=[round1, final])

            agent = AgentCore()
            agent.tool_executor = MagicMock()
            agent.tool_executor.execute = AsyncMock(return_value={})

            _ = await agent.process_message(sample_user, "Test")

        # Tool executor called with empty dict (due to JSON parse failure)
        agent.tool_executor.execute.assert_called_once()
        call_kwargs = agent.tool_executor.execute.call_args.kwargs
        assert call_kwargs.get("arguments") == {}

    async def test_system_prompt_contains_user_context(self, sample_user):
        """The messages list starts with system prompt including user name."""
        mock_resp = llm_text_response("Hi!")
        captured_messages = []

        async def capture_completion(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_resp

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=capture_completion)

            agent = AgentCore()
            await agent.process_message(sample_user, "Hello")

        system_msg = captured_messages[0]
        assert system_msg["role"] == "system"
        assert "Test" in system_msg["content"]  # user's first_name
        assert "EUR" in system_msg["content"]

    async def test_conversation_history_is_included(self, sample_user):
        """Passing conversation_history adds those messages before the current one."""
        mock_resp = llm_text_response("Based on our conversation...")
        captured_messages = []

        async def capture_completion(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_resp

        history = [
            {"role": "user", "content": "How much this month?"},
            {"role": "assistant", "content": "You spent 50 EUR."},
        ]

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=capture_completion)

            agent = AgentCore()
            await agent.process_message(
                sample_user, "Break down by store", conversation_history=history
            )

        # Messages: system, history[0], history[1], current user message
        assert captured_messages[1]["content"] == "How much this month?"
        assert captured_messages[2]["content"] == "You spent 50 EUR."
        assert captured_messages[3]["content"] == "Break down by store"

    async def test_tool_definitions_passed_to_llm(self, sample_user):
        """tools=TOOL_DEFINITIONS is passed in the litellm call."""
        mock_resp = llm_text_response("Hello!")
        captured_kwargs = {}

        async def capture_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        with (
            patch("src.agent.core.litellm") as mock_litellm,
            patch("src.agent.core.settings") as mock_settings,
        ):
            mock_settings.gemini_api_key = "test"
            mock_settings.openai_api_key = "test"
            mock_settings.conversational_model = "test-model"
            mock_litellm.acompletion = AsyncMock(side_effect=capture_completion)

            agent = AgentCore()
            await agent.process_message(sample_user, "Hello")

        assert "tools" in captured_kwargs
        assert len(captured_kwargs["tools"]) == 13
