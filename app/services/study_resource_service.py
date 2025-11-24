"""Service layer for study resource utilities exposed via the public API."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from app.database import (
    CrossReferenceRepository,
    DevotionalTemplateRepository,
    ReadingPlanRepository,
    TopicIndexRepository,
)
from app.utils.exceptions import ValidationError


class StudyResourceService:
    """Coordinates study resource lookups without invoking external APIs."""

    MAX_TOPIC_RESULTS = 50

    def get_cross_references(self, book: str, chapter: int, verse: int) -> Dict[str, object]:
        if not book or not isinstance(book, str):
            raise ValidationError("book is required")
        if chapter <= 0 or verse <= 0:
            raise ValidationError("chapter and verse must be positive integers")

        entries = CrossReferenceRepository.get_cross_references(book.strip(), chapter, verse)
        if not entries:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cross references found")
        return {
            "book": book.strip(),
            "chapter": chapter,
            "verse": verse,
            "references": entries,
        }

    def search_topics(self, keyword: Optional[str] = None, limit: int = 10) -> Dict[str, object]:
        limit = max(1, min(int(limit), self.MAX_TOPIC_RESULTS))
        normalized = keyword.strip() if isinstance(keyword, str) and keyword.strip() else None
        results = TopicIndexRepository.search_topics(normalized, limit)
        return {"keyword": normalized, "results": results}

    def list_reading_plans(self) -> List[Dict[str, object]]:
        plans = ReadingPlanRepository.list_plans()
        formatted = []
        for plan in plans:
            formatted.append(
                {
                    "slug": plan["slug"],
                    "name": plan["name"],
                    "description": plan.get("description"),
                    "duration_days": plan["duration_days"],
                    "metadata": plan.get("metadata", {}),
                }
            )
        return formatted

    def get_reading_plan(self, slug: str, days: Optional[int] = None, start_date: Optional[str] = None) -> Dict[str, object]:
        if not slug:
            raise ValidationError("plan slug is required")

        plan = ReadingPlanRepository.get_plan_by_slug(slug)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading plan not found")

        days_limit = None
        if days is not None:
            days_limit = max(1, min(int(days), plan["duration_days"]))

        schedule = ReadingPlanRepository.get_plan_schedule(plan["id"], max_days=days_limit)

        personalized_schedule = []
        base_date: Optional[date] = None
        if start_date:
            try:
                base_date = date.fromisoformat(start_date)
            except ValueError as err:
                raise ValidationError("start_date must be YYYY-MM-DD") from err

        for idx, step in enumerate(schedule, start=1):
            scheduled_on = None
            if base_date:
                scheduled_on = (base_date + timedelta(days=idx - 1)).isoformat()
            personalized_schedule.append({**step, "scheduled_date": scheduled_on})

        plan_meta = {
            "slug": plan["slug"],
            "name": plan["name"],
            "description": plan.get("description"),
            "duration_days": plan["duration_days"],
            "metadata": plan.get("metadata", {}),
        }

        return {"plan": plan_meta, "schedule": personalized_schedule}

    def list_devotional_templates(self) -> List[Dict[str, object]]:
        templates = DevotionalTemplateRepository.list_templates()
        formatted = []
        for template in templates:
            formatted.append(
                {
                    "slug": template["slug"],
                    "title": template["title"],
                    "body": template["body"],
                    "prompt_1": template["prompt_1"],
                    "prompt_2": template["prompt_2"],
                    "default_passage": template.get("default_passage"),
                    "metadata": template.get("metadata", {}),
                }
            )
        return formatted

    def generate_devotional(
        self,
        topic: str,
        template_slug: str = "classic",
        passage: Optional[str] = None,
        plan_slug: Optional[str] = None,
        day: Optional[int] = None,
    ) -> Dict[str, object]:
        if not topic:
            raise ValidationError("topic is required")

        template = DevotionalTemplateRepository.get_template(template_slug)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        supporting_reading = None
        if plan_slug and day:
            if day <= 0:
                raise ValidationError("day must be positive")
            plan = ReadingPlanRepository.get_plan_by_slug(plan_slug)
            if plan:
                schedule = ReadingPlanRepository.get_plan_schedule(plan["id"], max_days=day)
                if len(schedule) >= day:
                    supporting_reading = schedule[day - 1]

        resolved_passage = passage.strip() if passage else template.get("default_passage")
        reflection_questions = [
            template["prompt_1"].format(topic=topic),
            template["prompt_2"].format(topic=topic),
        ]

        return {
            "title": template["title"].format(topic=topic),
            "passage": resolved_passage,
            "summary": template["body"].format(topic=topic, passage=resolved_passage),
            "reflection_questions": reflection_questions,
            "supporting_reading": supporting_reading,
        }


def get_study_resource_service() -> StudyResourceService:
    return StudyResourceService()
