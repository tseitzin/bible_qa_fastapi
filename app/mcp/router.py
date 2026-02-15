"""FastAPI router exposing MCP-compatible endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import get_current_user_optional_dependency
from app.config import Settings, get_settings
from app.mcp.models import (
    MCPContext,
    MCPInvokeRequest,
    MCPInvokeResponse,
    MCPListToolsResponse,
)
from app.mcp.tool_registry import get_tool_definition, list_tools
from app.utils.exceptions import ValidationError

# Ensure all tools register themselves with the global registry.
from . import tools as _loaded_tools  # noqa: F401  pylint: disable=unused-import

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def _authorize_mcp(request: Request, settings: Settings = Depends(get_settings)) -> bool:
    """Enforce optional MCP API key protection."""
    api_key = settings.mcp_api_key.strip()
    if not api_key:
        return True

    provided = request.headers.get("x-mcp-api-key")
    if provided != api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MCP API key")

    return True


@router.get("/tools", response_model=MCPListToolsResponse)
async def list_registered_tools(_: bool = Depends(_authorize_mcp)) -> MCPListToolsResponse:
    """Return all MCP tool definitions so the LLM can introspect capabilities."""
    return MCPListToolsResponse(tools=list_tools())


@router.post("/call")
async def invoke_tool(
    payload: MCPInvokeRequest,
    _: bool = Depends(_authorize_mcp),
    current_user: Optional[dict] = Depends(get_current_user_optional_dependency),
):
    """Invoke a registered tool with the provided arguments."""
    definition = get_tool_definition(payload.tool)
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown MCP tool")

    try:
        context = MCPContext(user=current_user)
        result = definition.handler(payload.arguments, context)
        return MCPInvokeResponse(tool=payload.tool, success=True, result=result)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("MCP tool '%s' failed", payload.tool)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tool execution failed") from exc
