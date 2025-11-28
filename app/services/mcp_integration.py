"""Integration layer between MCP tools and OpenAI function calling."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.mcp.models import MCPContext
from app.mcp.tool_registry import get_tool_definition, list_tools

logger = logging.getLogger(__name__)


def get_bible_tools_for_openai() -> List[Dict[str, Any]]:
    """Convert MCP Bible tool schemas to OpenAI function calling format.
    
    Returns:
        List of tool definitions in OpenAI's function calling format.
    """
    mcp_tools = list_tools()
    openai_tools = []
    
    # Only include Bible retrieval tools for now
    bible_tool_names = {"get_verse", "get_passage", "get_chapter", "search_verses"}
    
    for mcp_tool in mcp_tools:
        if mcp_tool.name not in bible_tool_names:
            continue
            
        openai_tool = {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description,
                "parameters": mcp_tool.input_schema
            }
        }
        openai_tools.append(openai_tool)
    
    return openai_tools


def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any], user: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute an MCP tool and return the result.
    
    Args:
        tool_name: Name of the MCP tool to execute
        arguments: Arguments to pass to the tool
        user: Optional user context for authentication
        
    Returns:
        Dictionary containing the tool result
        
    Raises:
        ValueError: If the tool doesn't exist or execution fails
    """
    tool_def = get_tool_definition(tool_name)
    if not tool_def:
        raise ValueError(f"Tool '{tool_name}' not found")
    
    try:
        context = MCPContext(user=user)
        result = tool_def.handler(arguments, context)
        
        # Ensure result is JSON serializable
        if isinstance(result, dict):
            return result
        elif isinstance(result, (list, str, int, float, bool, type(None))):
            return {"result": result}
        else:
            return {"result": str(result)}
            
    except Exception as e:
        logger.error(f"Error executing MCP tool '{tool_name}': {e}")
        raise ValueError(f"Tool execution failed: {str(e)}")
