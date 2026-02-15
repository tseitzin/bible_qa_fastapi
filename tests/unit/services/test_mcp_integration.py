"""Tests for MCP integration service."""
import pytest
from unittest.mock import patch, Mock, MagicMock

from app.services.mcp_integration import get_bible_tools_for_openai, execute_mcp_tool


class TestGetBibleToolsForOpenAI:

    @patch("app.services.mcp_integration.list_tools")
    def test_converts_bible_tools_to_openai_format(self, mock_list):
        mock_tool = Mock()
        mock_tool.name = "get_verse"
        mock_tool.description = "Get a Bible verse"
        mock_tool.input_schema = {"type": "object", "properties": {"ref": {"type": "string"}}}

        non_bible_tool = Mock()
        non_bible_tool.name = "get_user_history"

        mock_list.return_value = [mock_tool, non_bible_tool]

        result = get_bible_tools_for_openai()

        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "get_verse"
        assert result[0]["function"]["description"] == "Get a Bible verse"

    @patch("app.services.mcp_integration.list_tools")
    def test_includes_all_bible_tool_types(self, mock_list):
        tools = []
        for name in ["get_verse", "get_passage", "get_chapter", "search_verses"]:
            t = Mock()
            t.name = name
            t.description = f"desc for {name}"
            t.input_schema = {"type": "object"}
            tools.append(t)

        mock_list.return_value = tools

        result = get_bible_tools_for_openai()

        assert len(result) == 4

    @patch("app.services.mcp_integration.list_tools")
    def test_returns_empty_when_no_bible_tools(self, mock_list):
        non_bible = Mock()
        non_bible.name = "other_tool"
        mock_list.return_value = [non_bible]

        result = get_bible_tools_for_openai()

        assert result == []


class TestExecuteMCPTool:

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_executes_tool_successfully(self, mock_get_tool):
        mock_handler = Mock(return_value={"text": "In the beginning..."})
        mock_tool = Mock()
        mock_tool.handler = mock_handler
        mock_get_tool.return_value = mock_tool

        result = execute_mcp_tool("get_verse", {"ref": "Genesis 1:1"})

        assert result == {"text": "In the beginning..."}

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_wraps_non_dict_results(self, mock_get_tool):
        mock_tool = Mock()
        mock_tool.handler = Mock(return_value="plain string")
        mock_get_tool.return_value = mock_tool

        result = execute_mcp_tool("test_tool", {})

        assert result == {"result": "plain string"}

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_wraps_list_results(self, mock_get_tool):
        mock_tool = Mock()
        mock_tool.handler = Mock(return_value=[1, 2, 3])
        mock_get_tool.return_value = mock_tool

        result = execute_mcp_tool("test_tool", {})

        assert result == {"result": [1, 2, 3]}

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_tool_not_found(self, mock_get_tool):
        mock_get_tool.return_value = None

        with pytest.raises(ValueError, match="not found"):
            execute_mcp_tool("nonexistent_tool", {})

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_tool_execution_error(self, mock_get_tool):
        mock_tool = Mock()
        mock_tool.handler = Mock(side_effect=Exception("Tool crashed"))
        mock_get_tool.return_value = mock_tool

        with pytest.raises(ValueError, match="Tool execution failed"):
            execute_mcp_tool("buggy_tool", {})

    @patch("app.services.mcp_integration.get_tool_definition")
    def test_passes_user_context(self, mock_get_tool):
        mock_tool = Mock()
        mock_tool.handler = Mock(return_value={"ok": True})
        mock_get_tool.return_value = mock_tool

        user = {"id": 1, "email": "test@example.com"}
        execute_mcp_tool("test_tool", {}, user=user)

        # Verify MCPContext was created with user
        call_args = mock_tool.handler.call_args
        context = call_args[0][1]
        assert context.user == user
