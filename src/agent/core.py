"""Core LLM agent loop: processes messages, executes tool calls, returns responses."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import litellm

from src.agent.prompts import build_system_prompt
from src.agent.tool_executor import ToolExecutor
from src.agent.tools import TOOL_DEFINITIONS
from src.config import settings
from src.db.models import User

logger = logging.getLogger(__name__)

# Maximum number of tool-call rounds before forcing a final response
MAX_TOOL_ROUNDS = 10


class AgentCore:
    """The central LLM agent that processes user messages through tool-calling."""

    def __init__(self) -> None:
        self.tool_executor = ToolExecutor()

        # Set API keys for LiteLLM (provider-specific via environment)
        import os

        if settings.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
        if settings.gemini_api_key:
            os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)

    async def process_message(
        self,
        user: User,
        message_text: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Process a user message through the LLM agent loop.

        The loop:
        1. Send user message + tools to the LLM
        2. If the LLM wants to call tool(s), execute them and send results back
        3. Repeat until the LLM produces a final text response (or max rounds reached)

        Args:
            user: The database User object for context.
            message_text: The user's text message.
            conversation_history: Optional prior messages for multi-turn context.

        Returns:
            The agent's final text response to send to the user.
        """
        # Build messages list
        system_prompt = build_system_prompt(
            user_name=user.first_name or user.username or "User",
            user_id=str(user.id),
            currency=user.currency,
            timezone=user.timezone,
            current_date=datetime.now(UTC).strftime("%Y-%m-%d"),
        )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add the current user message
        messages.append({"role": "user", "content": message_text})

        # Agent loop: call LLM, execute tools, repeat
        for round_num in range(MAX_TOOL_ROUNDS):
            logger.debug("Agent round %d for user %s", round_num + 1, user.telegram_id)

            try:
                response = await litellm.acompletion(
                    model=settings.conversational_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2048,
                )
            except Exception:
                logger.exception("LLM API call failed in round %d", round_num + 1)
                return "Sorry, I'm having trouble connecting to my AI service right now. Please try again in a moment."

            choice = response.choices[0]
            assistant_message = choice.message

            # If the LLM produced a final text response (no tool calls), we're done
            if not assistant_message.tool_calls:
                final_text = assistant_message.content or ""
                logger.info(
                    "Agent finished in %d round(s) for user %s",
                    round_num + 1,
                    user.telegram_id,
                )
                return final_text

            # The LLM wants to call tools -- execute them
            # Add the assistant's message (with tool_calls) to the conversation
            messages.append(assistant_message.model_dump())

            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(
                    "Executing tool: %s(%s) for user %s",
                    function_name,
                    json.dumps(arguments, default=str)[:200],
                    user.telegram_id,
                )

                # Execute the tool
                try:
                    result = await self.tool_executor.execute(
                        tool_name=function_name,
                        arguments=arguments,
                        user=user,
                    )
                except Exception as e:
                    logger.exception("Tool execution failed: %s", function_name)
                    result = f"Error executing {function_name}: {e!s}"

                # Add tool result to conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str)
                        if not isinstance(result, str)
                        else result,
                    }
                )

        # If we exhausted all rounds, ask the LLM for a final response without tools
        logger.warning(
            "Agent reached max rounds (%d) for user %s",
            MAX_TOOL_ROUNDS,
            user.telegram_id,
        )
        messages.append(
            {
                "role": "user",
                "content": "Please provide your final response based on the information gathered so far.",
            }
        )

        try:
            response = await litellm.acompletion(
                model=settings.conversational_model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return (
                response.choices[0].message.content
                or "I wasn't able to complete your request. Please try rephrasing."
            )
        except Exception:
            logger.exception("Final LLM call failed")
            return "Sorry, something went wrong. Please try again."
