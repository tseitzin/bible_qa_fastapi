"""Phase 2 MCP tools for user-specific data interactions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.database import QuestionRepository, SavedAnswersRepository, UserNotesRepository
from app.mcp.models import MCPContext, MCPToolSchema
from app.mcp.tool_registry import register_tool
from app.utils.exceptions import ValidationError


def _coerce_tags(raw: Any) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError("tags must be provided as a list of strings")
    tags: List[str] = []
    for value in raw:
        if not isinstance(value, str):
            raise ValidationError("tags must only contain strings")
        normalized = value.strip()
        if normalized:
            tags.append(normalized)
    return tags


def _require_positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def _register_user_tools() -> None:
    register_tool(
        MCPToolSchema(
            name="save_answer",
            description="Save a generated answer to the user's library with optional tags for recall.",
            input_schema={
                "type": "object",
                "properties": {
                    "question_id": {"type": "integer", "minimum": 1},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional topical tags or verse citations."
                    },
                },
                "required": ["question_id"],
            },
        ),
        _handle_save_answer,
    )

    register_tool(
        MCPToolSchema(
            name="get_saved_answers",
            description="Retrieve the authenticated user's saved answers, optionally filtered by tag or keyword.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
                    "query": {"type": "string"},
                    "tag": {"type": "string"},
                },
            },
        ),
        _handle_get_saved_answers,
    )

    register_tool(
        MCPToolSchema(
            name="save_note",
            description="Attach a personal note or verse citation metadata to a question or saved answer.",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "minLength": 1},
                    "question_id": {"type": "integer", "minimum": 1},
                    "metadata": {"type": "object", "additionalProperties": True},
                    "source": {"type": "string", "description": "Optional identifier for note origin."},
                },
                "required": ["content"],
            },
        ),
        _handle_save_note,
    )

    register_tool(
        MCPToolSchema(
            name="get_notes",
            description="Fetch personal study notes previously stored through MCP interactions.",
            input_schema={
                "type": "object",
                "properties": {
                    "question_id": {"type": "integer", "minimum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                },
            },
        ),
        _handle_get_notes,
    )

    register_tool(
        MCPToolSchema(
            name="get_history",
            description="Retrieve the user's recent Bible Q&A history (questions and answers).",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                },
            },
        ),
        _handle_get_history,
    )


def _handle_save_answer(args: Dict[str, Any], context: MCPContext):
    user = context.require_user()
    question_id = _require_positive_int(args.get("question_id"), "question_id")
    tags = _coerce_tags(args.get("tags"))

    SavedAnswersRepository.save_answer(user_id=user["id"], question_id=question_id, tags=tags)
    saved_answers = SavedAnswersRepository.get_user_saved_answers(user_id=user["id"], limit=1)
    if not saved_answers:
        raise ValidationError("Failed to persist saved answer")
    return saved_answers[0]


def _handle_get_saved_answers(args: Dict[str, Any], context: MCPContext):
    user = context.require_user()
    limit = int(args.get("limit", 50) or 50)
    limit = max(1, min(limit, 500))
    query = args.get("query")
    tag = args.get("tag")

    if query or tag:
        saved_answers = SavedAnswersRepository.search_saved_answers(
            user_id=user["id"],
            query=query,
            tag=tag,
        )
    else:
        saved_answers = SavedAnswersRepository.get_user_saved_answers(user_id=user["id"], limit=limit)

    return {"saved_answers": saved_answers, "total": len(saved_answers)}


def _handle_save_note(args: Dict[str, Any], context: MCPContext):
    user = context.require_user()
    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValidationError("content must be a non-empty string")

    question_id: Optional[int] = args.get("question_id")
    if question_id is not None:
        question_id = _require_positive_int(question_id, "question_id")

    metadata = args.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValidationError("metadata must be an object if provided")

    source = args.get("source")
    if source is not None and not isinstance(source, str):
        raise ValidationError("source must be a string if provided")

    note = UserNotesRepository.create_note(
        user_id=user["id"],
        question_id=question_id,
        content=content.strip(),
        metadata=metadata,
        source=source or "mcp",
    )
    return note


def _handle_get_notes(args: Dict[str, Any], context: MCPContext):
    user = context.require_user()
    limit = int(args.get("limit", 50) or 50)
    limit = max(1, min(limit, 200))
    question_id: Optional[int] = args.get("question_id")
    if question_id is not None:
        question_id = _require_positive_int(question_id, "question_id")

    notes = UserNotesRepository.list_notes(
        user_id=user["id"],
        question_id=question_id,
        limit=limit,
    )
    return {"notes": notes, "total": len(notes)}


def _handle_get_history(args: Dict[str, Any], context: MCPContext):
    user = context.require_user()
    limit = int(args.get("limit", 10) or 10)
    limit = max(1, min(limit, 100))

    rows = QuestionRepository.get_question_history(user_id=user["id"], limit=limit)
    questions = [
        {
            "id": item["id"],
            "question": item["question"],
            "answer": item.get("answer"),
            "created_at": item["created_at"],
        }
        for item in rows
    ]
    return {"questions": questions, "total": len(questions)}


__all__ = [
    "_handle_save_answer",
    "_handle_get_saved_answers",
    "_handle_save_note",
    "_handle_get_notes",
    "_handle_get_history",
]


_register_user_tools()
