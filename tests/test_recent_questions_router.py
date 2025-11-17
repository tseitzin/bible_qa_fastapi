"""Tests for recent questions router."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user

client = TestClient(app)


@pytest.fixture
def auth_override():
    """Simulate an authenticated user for router tests."""
    def override_user():
        return {"id": 1, "is_active": True}

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@patch("app.routers.recent_questions.RecentQuestionsRepository.get_recent_questions")
def test_list_recent_questions(mock_get_recent, auth_override):
    mock_get_recent.return_value = [
        {"id": 1, "question": "What is grace?", "asked_at": "2025-11-16T00:00:00Z"}
    ]

    response = client.get("/api/users/me/recent-questions")
    assert response.status_code == 200
    data = response.json()
    assert data["recent_questions"][0]["question"] == "What is grace?"


@patch("app.routers.recent_questions.RecentQuestionsRepository.get_recent_questions")
@patch("app.routers.recent_questions.RecentQuestionsRepository.add_recent_question")
def test_add_recent_question_success(mock_add_recent, mock_get_recent, auth_override):
    mock_get_recent.return_value = [
        {"id": 2, "question": "What is faith?", "asked_at": "2025-11-16T00:00:00Z"}
    ]

    response = client.post("/api/users/me/recent-questions", json={"question": "  What is faith?  "})
    assert response.status_code == 200
    mock_add_recent.assert_called_once_with(1, "What is faith?")
    assert response.json()["recent_questions"][0]["question"] == "What is faith?"


def test_add_recent_question_empty(auth_override):
    response = client.post("/api/users/me/recent-questions", json={"question": "   "})
    assert response.status_code == 400


@patch("app.routers.recent_questions.RecentQuestionsRepository.delete_recent_question", return_value=False)
def test_delete_recent_question_not_found(mock_delete, auth_override):
    response = client.delete("/api/users/me/recent-questions/99")
    assert response.status_code == 404
    mock_delete.assert_called_once_with(1, 99)


@patch("app.routers.recent_questions.RecentQuestionsRepository.get_recent_questions")
@patch("app.routers.recent_questions.RecentQuestionsRepository.delete_recent_question", return_value=True)
def test_delete_recent_question_success(mock_delete, mock_get_recent, auth_override):
    mock_get_recent.return_value = [
        {"id": 3, "question": "What is love?", "asked_at": "2025-11-16T00:00:00Z"}
    ]

    response = client.delete("/api/users/me/recent-questions/3")
    assert response.status_code == 200
    assert response.json()["recent_questions"][0]["question"] == "What is love?"
