"""Central registry for MCP tool declarations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from app.mcp.models import MCPContext, MCPToolSchema


@dataclass
class ToolDefinition:
    """Pairing of tool schema metadata with its callable handler."""

    schema: MCPToolSchema
    handler: Callable[[Dict[str, Any], MCPContext], Any]


_tool_registry: Dict[str, ToolDefinition] = {}


def register_tool(schema: MCPToolSchema, handler: Callable[[Dict[str, Any], MCPContext], Any]) -> None:
    """Register a tool and its handler in the global registry."""
    _tool_registry[schema.name] = ToolDefinition(schema=schema, handler=handler)


def list_tools() -> list[MCPToolSchema]:
    """Return all registered tool schemas."""
    return [definition.schema for definition in _tool_registry.values()]


def get_tool_definition(tool_name: str) -> ToolDefinition | None:
    """Retrieve a tool definition by name."""
    return _tool_registry.get(tool_name)
