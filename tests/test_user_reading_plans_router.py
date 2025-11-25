"""Tests for user reading plan tracking endpoints."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user_dependency
from app.routers import user_reading_plans
from app.services.reading_plan_tracking_service import ReadingPlanTrackingService

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    return {"id": 42, "email": "user@example.com", "is_active": True}


def _mock_service() -> Mock:
    return Mock(spec=ReadingPlanTrackingService)


def _apply_common_overrides(service_mock: Mock, user: dict):
    app.dependency_overrides[get_current_user_dependency] = lambda: user
    app.dependency_overrides[user_reading_plans.get_reading_plan_tracking_service] = lambda: service_mock


def test_list_user_reading_plans_returns_payload(mock_user):
    service_mock = _mock_service()
    service_mock.list_user_plans.return_value = [
        {
            "id": 1,
            "plan": {
                "slug": "demo",
                "name": "Demo Plan",
                "description": "",
                "duration_days": 30,
                "metadata": {},
            },
            "start_date": "2025-01-01",
            "nickname": None,
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "completed_at": None,
            "completed_days": 0,
            "total_days": 30,
            "percent_complete": 0,
            "next_day_number": 1,
        }
    ]
    _apply_common_overrides(service_mock, mock_user)

    response = client.get("/api/user-reading-plans")

    assert response.status_code == 200
    assert response.json()[0]["plan"]["slug"] == "demo"
    service_mock.list_user_plans.assert_called_once_with(mock_user["id"])


def test_start_user_reading_plan_creates_entry(mock_user):
    service_mock = _mock_service()
    service_mock.start_plan.return_value = {
        "id": 2,
        "plan": {
            "slug": "chronological",
            "name": "Chronological",
            "description": "",
            "duration_days": 365,
            "metadata": {},
        },
        "start_date": "2025-02-01",
        "nickname": "Family",
        "is_active": True,
        "created_at": "2025-02-01T00:00:00",
        "completed_at": None,
        "completed_days": 0,
        "total_days": 365,
        "percent_complete": 0,
        "next_day_number": 1,
    }
    _apply_common_overrides(service_mock, mock_user)

    response = client.post(
        "/api/user-reading-plans",
        json={"plan_slug": "chronological", "nickname": "Family"},
    )

    assert response.status_code == 201
    assert response.json()["nickname"] == "Family"
    service_mock.start_plan.assert_called_once_with(
        user_id=mock_user["id"], plan_slug="chronological", start_date=None, nickname="Family"
    )


def test_get_user_reading_plan_detail_returns_schedule(mock_user):
    service_mock = _mock_service()
    service_mock.get_user_plan_detail.return_value = {
        "id": 3,
        "plan": {
            "slug": "demo",
            "name": "Demo Plan",
            "description": "",
            "duration_days": 5,
            "metadata": {},
        },
        "start_date": "2025-03-01",
        "nickname": None,
        "is_active": True,
        "created_at": "2025-03-01T00:00:00",
        "completed_at": None,
        "completed_days": 1,
        "total_days": 5,
        "percent_complete": 20.0,
        "next_day_number": 2,
        "schedule": [
            {
                "day_number": 1,
                "title": "Intro",
                "passage": "John 1",
                "notes": None,
                "metadata": {},
                "scheduled_date": "2025-03-01",
                "is_complete": True,
                "completed_at": "2025-03-01T12:00:00",
            }
        ],
    }
    _apply_common_overrides(service_mock, mock_user)

    response = client.get("/api/user-reading-plans/3")

    assert response.status_code == 200
    assert response.json()["schedule"][0]["day_number"] == 1
    service_mock.get_user_plan_detail.assert_called_once_with(user_id=mock_user["id"], user_plan_id=3)


def test_update_user_reading_plan_day_returns_status(mock_user):
    service_mock = _mock_service()
    service_mock.update_day_completion.return_value = {
        "day_number": 4,
        "is_complete": True,
        "completed_at": "2025-04-04T10:00:00",
        "completed_days": 4,
        "total_days": 30,
        "percent_complete": 13.33,
        "plan_completed_at": None,
    }
    _apply_common_overrides(service_mock, mock_user)

    response = client.patch(
        "/api/user-reading-plans/7/days/4",
        json={"is_complete": True},
    )

    assert response.status_code == 200
    assert response.json()["day_number"] == 4
    service_mock.update_day_completion.assert_called_once_with(
        user_id=mock_user["id"], user_plan_id=7, day_number=4, is_complete=True
    )


def test_delete_user_reading_plan_returns_no_content(mock_user):
    service_mock = _mock_service()
    _apply_common_overrides(service_mock, mock_user)

    response = client.delete("/api/user-reading-plans/9")

    assert response.status_code == 204
    assert response.content == b""
    service_mock.delete_plan.assert_called_once_with(user_id=mock_user["id"], user_plan_id=9)
