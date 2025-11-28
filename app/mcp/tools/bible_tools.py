"""Phase 1 MCP tools for scripture retrieval."""
from __future__ import annotations

from typing import Any, Dict

from app.mcp.models import MCPContext, MCPToolSchema
from app.mcp.tool_registry import register_tool
from app.services.bible_service import get_bible_service
from app.utils.exceptions import ValidationError


def _validate_required_arguments(args: Dict[str, Any], required_fields: list[str]) -> None:
    missing = [field for field in required_fields if args.get(field) in (None, "")]
    if missing:
        raise ValidationError(f"Missing required argument(s): {', '.join(missing)}")


def _register_scripture_tools() -> None:
    register_tool(
        MCPToolSchema(
            name="get_verse",
            description="Retrieve an exact King James Version verse, ensuring accurate citation.",
            input_schema={
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "Bible book (e.g., 'John')."},
                    "chapter": {"type": "integer", "minimum": 1},
                    "verse": {"type": "integer", "minimum": 1},
                },
                "required": ["book", "chapter", "verse"],
            },
        ),
        _handle_get_verse,
    )

    register_tool(
        MCPToolSchema(
            name="get_passage",
            description="Retrieve a range of verses within a single chapter (ideal for short passages).",
            input_schema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "integer", "minimum": 1},
                    "start_verse": {"type": "integer", "minimum": 1},
                    "end_verse": {"type": "integer", "minimum": 1},
                },
                "required": ["book", "chapter", "start_verse", "end_verse"],
            },
        ),
        _handle_get_passage,
    )

    register_tool(
        MCPToolSchema(
            name="get_chapter",
            description="Fetch an entire chapter to provide broader context for an answer.",
            input_schema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "integer", "minimum": 1},
                },
                "required": ["book", "chapter"],
            },
        ),
        _handle_get_chapter,
    )

    register_tool(
        MCPToolSchema(
            name="search_verses",
            description="Search for verses containing a keyword or short phrase (case-insensitive).",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "minLength": 2},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 20},
                },
                "required": ["keyword"],
            },
        ),
        _handle_search_verses,
    )


def _handle_get_verse(args: Dict[str, Any], _: MCPContext):
    _validate_required_arguments(args, ["book", "chapter", "verse"])
    reference = f"{args['book']} {args['chapter']}:{args['verse']}"
    service = get_bible_service()
    result = service.get_verse(reference)
    if not result:
        raise ValidationError("Verse not found")
    return result


def _handle_get_passage(args: Dict[str, Any], _: MCPContext):
    _validate_required_arguments(args, ["book", "chapter", "start_verse", "end_verse"])
    service = get_bible_service()
    passage = service.get_passage(
        book=args["book"],
        chapter=args["chapter"],
        start_verse=args["start_verse"],
        end_verse=args["end_verse"],
    )
    if not passage:
        raise ValidationError("Passage not found")
    return passage


def _handle_get_chapter(args: Dict[str, Any], _: MCPContext):
    _validate_required_arguments(args, ["book", "chapter"])
    service = get_bible_service()
    chapter = service.get_chapter(book=args["book"], chapter=args["chapter"])
    if not chapter:
        raise ValidationError("Chapter not found")
    return chapter


def _handle_search_verses(args: Dict[str, Any], _: MCPContext):
    _validate_required_arguments(args, ["keyword"])
    service = get_bible_service()
    limit = args.get("limit", 20)
    return service.search_verses(keyword=args["keyword"], limit=limit)


_register_scripture_tools()
