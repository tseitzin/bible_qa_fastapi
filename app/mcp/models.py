"""Pydantic models and helpers for MCP tooling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.utils.exceptions import ValidationError


class MCPToolSchema(BaseModel):
    """Schema metadata describing an available MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class MCPListToolsResponse(BaseModel):
    """Response payload containing all tool definitions."""

    tools: list[MCPToolSchema]


class MCPInvokeRequest(BaseModel):
    """Request payload for invoking a tool."""

    tool: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPInvokeResponse(BaseModel):
    """Standardized invocation response."""

    model_config = {"arbitrary_types_allowed": True}

    tool: str
    success: bool = True
    result: Optional[Union[Dict[str, Any], List[Any]]] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


@dataclass
class MCPContext:
    """Runtime context passed to MCP tool handlers."""

    user: Optional[dict] = None

    def require_user(self) -> dict:
        """Return the authenticated user or raise."""
        if not self.user:
            raise ValidationError("Authentication required for this tool.")
        return self.user
