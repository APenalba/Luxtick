"""Unit tests for structural validation of LLM tool definitions."""

import pytest

from src.agent.tool_executor import ToolExecutor
from src.agent.tools import TOOL_DEFINITIONS

pytestmark = pytest.mark.unit


class TestToolDefinitions:
    def test_all_tools_have_type_function(self):
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function", f"Tool missing type=function: {tool}"

    def test_all_tools_have_name(self):
        for tool in TOOL_DEFINITIONS:
            name = tool["function"]["name"]
            assert isinstance(name, str) and len(name) > 0

    def test_all_tools_have_description(self):
        for tool in TOOL_DEFINITIONS:
            desc = tool["function"]["description"]
            assert isinstance(desc, str) and len(desc) > 10

    def test_all_tools_have_parameters(self):
        for tool in TOOL_DEFINITIONS:
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params

    def test_tool_count_is_13(self):
        assert len(TOOL_DEFINITIONS) == 13

    def test_required_fields_are_lists(self):
        for tool in TOOL_DEFINITIONS:
            params = tool["function"]["parameters"]
            if "required" in params:
                assert isinstance(params["required"], list)

    def test_tool_names_match_executor(self):
        executor = ToolExecutor()
        tool_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        handler_names = set(executor._handlers.keys())
        assert tool_names == handler_names, (
            f"Mismatch: tools={tool_names - handler_names}, handlers={handler_names - tool_names}"
        )
