"""Phase 3 MCP tools for advanced study utilities."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.database import (
    CrossReferenceRepository,
    DevotionalTemplateRepository,
    LexiconRepository,
    ReadingPlanRepository,
    TopicIndexRepository,
)
from app.mcp.models import MCPContext, MCPToolSchema
from app.mcp.tool_registry import register_tool
from app.utils.exceptions import ValidationError


def _validate_positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def _normalize_keyword(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _register_utility_tools() -> None:
    register_tool(
        MCPToolSchema(
            name="get_cross_references",
            description="Return Treasury of Scripture Knowledge cross references for a verse.",
            input_schema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "integer", "minimum": 1},
                    "verse": {"type": "integer", "minimum": 1},
                },
                "required": ["book", "chapter", "verse"],
            },
        ),
        _handle_get_cross_references,
    )

    register_tool(
        MCPToolSchema(
            name="lexicon_lookup",
            description="Look up Strong's lexicon data (lemma, transliteration, definitions, usage).",
            input_schema={
                "type": "object",
                "properties": {
                    "strongs_number": {"type": "string"},
                    "lemma": {"type": "string"},
                },
                "anyOf": [
                    {"required": ["strongs_number"]},
                    {"required": ["lemma"]},
                ],
            },
        ),
        _handle_lexicon_lookup,
    )

    register_tool(
        MCPToolSchema(
            name="topic_search",
            description="Search a topical index for passages grouped by theme.",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "minLength": 2},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                },
                "required": ["keyword"],
            },
        ),
        _handle_topic_search,
    )

    register_tool(
        MCPToolSchema(
            name="generate_reading_plan",
            description="Return a curated multi-day Bible reading plan by slug (e.g., 'gospels-in-30-days').",
            input_schema={
                "type": "object",
                "properties": {
                    "plan_slug": {"type": "string"},
                    "days": {"type": "integer", "minimum": 1, "maximum": 120},
                    "start_date": {"type": "string", "description": "ISO date to personalize calendar (optional)."},
                },
                "required": ["plan_slug"],
            },
        ),
        _handle_generate_reading_plan,
    )

    register_tool(
        MCPToolSchema(
            name="generate_devotional",
            description="Produce a simple devotional outline using stored templates and topical metadata (no external API calls).",
            input_schema={
                "type": "object",
                "properties": {
                    "template_slug": {"type": "string", "default": "classic"},
                    "topic": {"type": "string"},
                    "passage": {"type": "string"},
                    "plan_slug": {"type": "string"},
                    "day": {"type": "integer", "minimum": 1},
                },
                "required": ["topic"],
            },
        ),
        _handle_generate_devotional,
    )


def _handle_get_cross_references(args: Dict[str, Any], _: MCPContext):
    book = _normalize_keyword(args.get("book"), "book")
    chapter = _validate_positive_int(args.get("chapter"), "chapter")
    verse = _validate_positive_int(args.get("verse"), "verse")

    entries = CrossReferenceRepository.get_cross_references(book, chapter, verse)
    if not entries:
        raise ValidationError("No cross references found for the supplied verse")
    return {"book": book, "chapter": chapter, "verse": verse, "references": entries}


def _handle_lexicon_lookup(args: Dict[str, Any], _: MCPContext):
    strongs_number = args.get("strongs_number")
    lemma = args.get("lemma")

    if strongs_number:
        strongs_number = _normalize_keyword(strongs_number, "strongs_number")
    if lemma:
        lemma = _normalize_keyword(lemma, "lemma")

    entry = LexiconRepository.get_entry(strongs_number=strongs_number, lemma=lemma)
    if not entry:
        raise ValidationError("No lexicon entry found for the supplied query")
    return entry


def _handle_topic_search(args: Dict[str, Any], _: MCPContext):
    keyword = _normalize_keyword(args.get("keyword"), "keyword")
    limit = args.get("limit", 10)
    limit = max(1, min(int(limit), 25))

    matches = TopicIndexRepository.search_topics(keyword=keyword, limit=limit)
    return {"keyword": keyword, "results": matches}


def _handle_generate_reading_plan(args: Dict[str, Any], _: MCPContext):
    plan_slug = _normalize_keyword(args.get("plan_slug"), "plan_slug")
    plan = ReadingPlanRepository.get_plan_by_slug(plan_slug)
    if not plan:
        raise ValidationError("Unknown reading plan slug")

    days_limit = args.get("days")
    if days_limit is not None:
        days_limit = max(1, min(int(days_limit), plan["duration_days"]))
    steps = ReadingPlanRepository.get_plan_schedule(plan["id"], max_days=days_limit)

    start_date_raw = args.get("start_date")
    personalized_schedule: List[Dict[str, Any]] = []
    base_date: Optional[date] = None
    if start_date_raw:
        try:
            base_date = date.fromisoformat(start_date_raw)
        except ValueError as err:
            raise ValidationError("start_date must be ISO formatted (YYYY-MM-DD)") from err

    for index, step in enumerate(steps, start=1):
        scheduled_on = None
        if base_date:
            scheduled_on = (base_date + timedelta(days=index - 1)).isoformat()
        personalized_schedule.append({**step, "scheduled_date": scheduled_on})

    return {
        "plan": {
            "slug": plan["slug"],
            "name": plan["name"],
            "description": plan["description"],
            "duration_days": plan["duration_days"],
        },
        "schedule": personalized_schedule,
    }


def _handle_generate_devotional(args: Dict[str, Any], _: MCPContext):
    topic = _normalize_keyword(args.get("topic"), "topic")
    template_slug = _normalize_keyword(args.get("template_slug", "classic"), "template_slug")
    template = DevotionalTemplateRepository.get_template(template_slug)
    if not template:
        raise ValidationError("Unknown devotional template")

    passage = args.get("passage")
    if passage:
        passage = passage.strip()

    plan_slug = args.get("plan_slug")
    plan_day = args.get("day")
    plan_content: Optional[Dict[str, Any]] = None
    if plan_slug and plan_day:
        plan = ReadingPlanRepository.get_plan_by_slug(_normalize_keyword(plan_slug, "plan_slug"))
        if plan:
            steps = ReadingPlanRepository.get_plan_schedule(plan["id"], max_days=plan_day)
            plan_content = steps[plan_day - 1] if len(steps) >= plan_day else None

    reflection_points = [
        template["prompt_1"].format(topic=topic),
        template["prompt_2"].format(topic=topic),
    ]

    return {
        "title": template["title"].format(topic=topic),
        "passage": passage or template.get("default_passage"),
        "summary": template["body"].format(topic=topic, passage=passage or template.get("default_passage")),
        "reflection_questions": reflection_points,
        "supporting_reading": plan_content,
    }


__all__ = [
    "_handle_get_cross_references",
    "_handle_lexicon_lookup",
    "_handle_topic_search",
    "_handle_generate_reading_plan",
    "_handle_generate_devotional",
]


_register_utility_tools()
