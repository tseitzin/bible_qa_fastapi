"""API tests for study resources endpoints."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import study_resources
from app.services.study_resource_service import StudyResourceService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _mock_service(**methods):
    mock = Mock(spec=StudyResourceService)
    for name, value in methods.items():
        getattr(mock, name).return_value = value
    return mock


def test_get_cross_references_endpoint_returns_payload():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        get_cross_references={
            "book": "John",
            "chapter": 3,
            "verse": 16,
            "references": [{"reference": "Romans 5:8", "note": ""}],
        }
    )

    response = client.get(
        "/api/study/cross-references",
        params={"book": "John", "chapter": 3, "verse": 16},
    )

    assert response.status_code == 200
    assert response.json()["book"] == "John"


def test_get_topics_endpoint_returns_results():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        search_topics={
            "keyword": "faith",
            "results": [
                {
                    "topic": "Faith",
                    "summary": "",
                    "keywords": ["faith"],
                    "references": [],
                }
            ],
        }
    )

    response = client.get("/api/study/topics", params={"keyword": "faith"})

    assert response.status_code == 200
    assert response.json()["results"][0]["topic"] == "Faith"


def test_get_topics_endpoint_lists_default_when_keyword_missing():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        search_topics={
            "keyword": None,
            "results": [
                {
                    "topic": "Hope",
                    "summary": "",
                    "keywords": ["hope"],
                    "references": [],
                }
            ],
        }
    )

    response = client.get("/api/study/topics")

    assert response.status_code == 200
    assert response.json()["results"][0]["topic"] == "Hope"


def test_get_reading_plans_endpoint_lists_plans():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        list_reading_plans=[
            {
                "slug": "demo",
                "name": "Demo Plan",
                "description": "",
                "duration_days": 30,
                "metadata": {},
            }
        ]
    )

    response = client.get("/api/study/reading-plans")

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "demo"


def test_get_reading_plan_detail_endpoint_returns_schedule():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        get_reading_plan={
            "plan": {
                "slug": "demo",
                "name": "Demo Plan",
                "description": "",
                "duration_days": 5,
                "metadata": {},
            },
            "schedule": [
                {
                    "day_number": 1,
                    "title": "Start",
                    "passage": "John 1",
                    "notes": None,
                    "scheduled_date": None,
                    "metadata": {},
                }
            ],
        }
    )

    response = client.get("/api/study/reading-plans/demo")

    assert response.status_code == 200
    assert response.json()["schedule"][0]["day_number"] == 1


def test_get_devotional_templates_endpoint():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        list_devotional_templates=[
            {
                "slug": "classic",
                "title": "Classic",
                "body": "{topic}",
                "prompt_1": "{topic}?",
                "prompt_2": "{topic}!",
                "default_passage": "John 15",
                "metadata": {},
            }
        ]
    )

    response = client.get("/api/study/devotional-templates")

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "classic"


def test_post_devotional_endpoint_generates_outline():
    app.dependency_overrides[study_resources.get_study_resource_service] = lambda: _mock_service(
        generate_devotional={
            "title": "Hope Focus",
            "passage": "Colossians 1",
            "summary": "",
            "reflection_questions": ["Q1", "Q2"],
            "supporting_reading": None,
        }
    )

    response = client.post(
        "/api/study/devotionals",
        json={"topic": "Hope", "template_slug": "classic"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Hope Focus"
