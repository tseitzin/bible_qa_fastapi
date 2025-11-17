"""Tests for saved answers router."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user

client = TestClient(app)


@pytest.fixture
def auth_override():
    """Simulate an authenticated user."""
    def override_user():
        return {"id": 1, "is_active": True}

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_saved_answers")
@patch("app.routers.saved_answers.SavedAnswersRepository.save_answer")
def test_save_answer_success(mock_save, mock_get_saved, auth_override):
    mock_get_saved.return_value = [
        {
            "id": 15,
            "question_id": 3,
            "question": "Who is Jesus?",
            "answer": "Jesus is the Son of God.",
            "tags": ["christology"],
            "saved_at": "2025-11-16T00:00:00Z",
            "parent_question_id": None,
            "conversation_thread": [],
        }
    ]

    response = client.post(
        "/api/saved-answers",
        json={"question_id": 3, "tags": ["christology"]},
    )

    assert response.status_code == 201
    assert response.json()["question_id"] == 3
    mock_save.assert_called_once_with(user_id=1, question_id=3, tags=["christology"])


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_saved_answers", return_value=[])
@patch("app.routers.saved_answers.SavedAnswersRepository.save_answer")
def test_save_answer_failure(mock_save, mock_get_saved, auth_override):
    response = client.post("/api/saved-answers", json={"question_id": 4, "tags": []})
    assert response.status_code == 500


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_saved_answers")
def test_get_saved_answers_default(mock_get_saved, auth_override):
    mock_get_saved.return_value = []
    response = client.get("/api/saved-answers")
    assert response.status_code == 200
    mock_get_saved.assert_called_once_with(user_id=1, limit=100)


@patch("app.routers.saved_answers.SavedAnswersRepository.search_saved_answers")
def test_get_saved_answers_with_filters(mock_search, auth_override):
    mock_search.return_value = []
    response = client.get("/api/saved-answers", params={"query": "love", "tag": "faith"})
    assert response.status_code == 200
    mock_search.assert_called_once_with(user_id=1, query="love", tag="faith")


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_saved_answers", side_effect=Exception("db error"))
def test_get_saved_answers_error(mock_get_saved, auth_override):
    response = client.get("/api/saved-answers")
    assert response.status_code == 500


@patch("app.routers.saved_answers.SavedAnswersRepository.delete_saved_answer", return_value=False)
def test_delete_saved_answer_not_found(mock_delete, auth_override):
    response = client.delete("/api/saved-answers/99")
    assert response.status_code == 404
    mock_delete.assert_called_once_with(user_id=1, saved_answer_id=99)


@patch("app.routers.saved_answers.SavedAnswersRepository.delete_saved_answer", return_value=True)
def test_delete_saved_answer_success(mock_delete, auth_override):
    response = client.delete("/api/saved-answers/1")
    assert response.status_code == 204
    mock_delete.assert_called_once_with(user_id=1, saved_answer_id=1)


@patch("app.routers.saved_answers.SavedAnswersRepository.delete_saved_answer", side_effect=Exception("db error"))
def test_delete_saved_answer_server_error(mock_delete, auth_override):
    response = client.delete("/api/saved-answers/1")
    assert response.status_code == 500


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_tags", return_value=["faith", "hope"])
def test_get_tags_success(mock_get_tags, auth_override):
    response = client.get("/api/saved-answers/tags")
    assert response.status_code == 200
    assert response.json() == ["faith", "hope"]


@patch("app.routers.saved_answers.SavedAnswersRepository.get_user_tags", side_effect=Exception("db error"))
def test_get_tags_failure(mock_get_tags, auth_override):
    response = client.get("/api/saved-answers/tags")
    assert response.status_code == 500
