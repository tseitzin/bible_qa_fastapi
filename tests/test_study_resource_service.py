"""Unit tests for StudyResourceService logic."""
from datetime import date

import pytest
from fastapi import HTTPException

from app.services.study_resource_service import StudyResourceService, get_study_resource_service
from app.database import (
    CrossReferenceRepository,
    TopicIndexRepository,
    ReadingPlanRepository,
    DevotionalTemplateRepository,
)
from app.utils.exceptions import ValidationError


@pytest.fixture
def service():
    return StudyResourceService()


def test_get_cross_references_returns_payload(monkeypatch, service):
    monkeypatch.setattr(
        CrossReferenceRepository,
        "get_cross_references",
        lambda book, chapter, verse: [
            {"reference": "Romans 5:8", "note": "God's love"}
        ],
    )

    payload = service.get_cross_references("John", 3, 16)

    assert payload["book"] == "John"
    assert payload["references"][0]["reference"] == "Romans 5:8"


def test_get_cross_references_not_found(monkeypatch, service):
    monkeypatch.setattr(
        CrossReferenceRepository,
        "get_cross_references",
        lambda *args, **kwargs: [],
    )

    with pytest.raises(HTTPException) as exc:
        service.get_cross_references("John", 3, 16)

    assert exc.value.status_code == 404


def test_get_cross_references_validates_inputs(service):
    with pytest.raises(ValidationError):
        service.get_cross_references("", 1, 1)

    with pytest.raises(ValidationError):
        service.get_cross_references("John", 0, 1)


def test_search_topics_clamps_limit(monkeypatch, service):
    captured = {}

    def fake_search(keyword, limit):
        captured["keyword"] = keyword
        captured["limit"] = limit
        return [
            {
                "topic": "Faith",
                "summary": "",
                "keywords": ["faith"],
                "references": [],
            }
        ]

    monkeypatch.setattr(TopicIndexRepository, "search_topics", fake_search)

    payload = service.search_topics("faith", limit=999)

    assert payload["keyword"] == "faith"
    assert captured["limit"] == service.MAX_TOPIC_RESULTS

def test_search_topics_allows_missing_keyword(monkeypatch, service):
    captured = {}

    def fake_search(keyword, limit):
        captured["keyword"] = keyword
        return [
            {
                "topic": "Hope",
                "summary": "",
                "keywords": ["hope"],
                "references": [],
            }
        ]

    monkeypatch.setattr(TopicIndexRepository, "search_topics", fake_search)

    payload = service.search_topics(None)

    assert payload["keyword"] is None
    assert captured["keyword"] is None


def test_list_reading_plans_formats_metadata(monkeypatch, service):
    monkeypatch.setattr(
        ReadingPlanRepository,
        "list_plans",
        lambda: [
            {
                "id": 1,
                "slug": "demo",
                "name": "Demo Plan",
                "description": "",
                "duration_days": 5,
                "metadata": {"level": "easy"},
            }
        ],
    )

    plans = service.list_reading_plans()

    assert plans[0]["slug"] == "demo"
    assert plans[0]["metadata"]["level"] == "easy"


def test_get_reading_plan_requires_slug(service):
    with pytest.raises(ValidationError):
        service.get_reading_plan("")


def test_get_reading_plan_adds_schedule_dates(monkeypatch, service):
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_by_slug",
        lambda slug: {
            "id": 99,
            "slug": slug,
            "name": "Demo",
            "description": "",
            "duration_days": 10,
            "metadata": {},
        },
    )
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_schedule",
        lambda plan_id, max_days=None: [
            {
                "day_number": 1,
                "title": "Start",
                "passage": "John 1",
                "notes": None,
                "metadata": {},
            }
        ],
    )

    payload = service.get_reading_plan("demo", days=1, start_date=date(2024, 1, 1).isoformat())

    assert payload["plan"]["slug"] == "demo"
    assert payload["schedule"][0]["scheduled_date"] == date(2024, 1, 1).isoformat()


def test_get_reading_plan_validates_start_date(monkeypatch, service):
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_by_slug",
        lambda slug: {
            "id": 1,
            "slug": slug,
            "name": "Demo",
            "description": "",
            "duration_days": 10,
            "metadata": {},
        },
    )
    monkeypatch.setattr(ReadingPlanRepository, "get_plan_schedule", lambda plan_id, max_days=None: [])

    with pytest.raises(ValidationError):
        service.get_reading_plan("demo", start_date="01-01-2024")


def test_get_reading_plan_missing_plan_raises(monkeypatch, service):
    monkeypatch.setattr(ReadingPlanRepository, "get_plan_by_slug", lambda slug: None)

    with pytest.raises(HTTPException) as exc:
        service.get_reading_plan("missing")

    assert exc.value.status_code == 404


def test_list_devotional_templates(monkeypatch, service):
    monkeypatch.setattr(
        DevotionalTemplateRepository,
        "list_templates",
        lambda: [
            {
                "slug": "classic",
                "title": "Classic",
                "body": "{topic}",
                "prompt_1": "{topic}?",
                "prompt_2": "{topic}!",
                "default_passage": "John 15",
                "metadata": {},
            }
        ],
    )

    templates = service.list_devotional_templates()

    assert templates[0]["slug"] == "classic"


def test_generate_devotional_uses_supporting_plan(monkeypatch, service):
    monkeypatch.setattr(
        DevotionalTemplateRepository,
        "get_template",
        lambda slug: {
            "slug": slug,
            "title": "{topic} Focus",
            "body": "Reflect on {topic} at {passage}",
            "prompt_1": "Where do you see {topic}?",
            "prompt_2": "How will you live {topic}?",
            "default_passage": "Colossians 1",
        },
    )
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_by_slug",
        lambda slug: {
            "id": 1,
            "slug": slug,
            "name": "Plan",
            "description": "",
            "duration_days": 30,
            "metadata": {},
        },
    )
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_schedule",
        lambda plan_id, max_days=None: [
            {
                "day_number": 1,
                "title": "Day 1",
                "passage": "John 1",
                "notes": None,
                "metadata": {},
            }
        ],
    )

    payload = service.generate_devotional(
        topic="Hope",
        template_slug="classic",
        plan_slug="plan",
        day=1,
    )

    assert payload["title"] == "Hope Focus"
    assert payload["supporting_reading"]["passage"] == "John 1"


def test_generate_devotional_defaults_to_template_passage(monkeypatch, service):
    monkeypatch.setattr(
        DevotionalTemplateRepository,
        "get_template",
        lambda slug: {
            "slug": slug,
            "title": "{topic} Focus",
            "body": "Reflect on {topic}",
            "prompt_1": "",
            "prompt_2": "",
            "default_passage": "Psalm 23",
        },
    )
    monkeypatch.setattr(ReadingPlanRepository, "get_plan_by_slug", lambda slug: None)

    payload = service.generate_devotional(topic="Love", template_slug="classic")

    assert payload["supporting_reading"] is None
    assert payload["passage"] == "Psalm 23"


def test_generate_devotional_requires_topic(service):
    with pytest.raises(ValidationError):
        service.generate_devotional(topic="")


def test_generate_devotional_missing_template(monkeypatch, service):
    monkeypatch.setattr(DevotionalTemplateRepository, "get_template", lambda slug: None)

    with pytest.raises(HTTPException) as exc:
        service.generate_devotional(topic="Joy", template_slug="missing")

    assert exc.value.status_code == 404


def test_generate_devotional_missing_schedule_returns_none(monkeypatch, service):
    monkeypatch.setattr(
        DevotionalTemplateRepository,
        "get_template",
        lambda slug: {
            "slug": slug,
            "title": "{topic}",
            "body": "",
            "prompt_1": "",
            "prompt_2": "",
            "default_passage": "Psalm 1",
        },
    )
    monkeypatch.setattr(
        ReadingPlanRepository,
        "get_plan_by_slug",
        lambda slug: {
            "id": 1,
            "slug": slug,
            "name": "Plan",
            "description": "",
            "duration_days": 30,
            "metadata": {},
        },
    )
    monkeypatch.setattr(ReadingPlanRepository, "get_plan_schedule", lambda plan_id, max_days=None: [])

    payload = service.generate_devotional(topic="Hope", template_slug="classic", plan_slug="plan", day=2)

    assert payload["supporting_reading"] is None


def test_generate_devotional_validates_day_when_using_plan(monkeypatch, service):
    monkeypatch.setattr(
        DevotionalTemplateRepository,
        "get_template",
        lambda slug: {
            "slug": slug,
            "title": "{topic}",
            "body": "{topic}",
            "prompt_1": "",
            "prompt_2": "",
            "default_passage": "Psalm 1",
        },
    )

    with pytest.raises(ValidationError):
        service.generate_devotional(topic="Hope", template_slug="classic", plan_slug="plan", day=-1)


def test_get_study_resource_service_factory_returns_instance():
    assert isinstance(get_study_resource_service(), StudyResourceService)