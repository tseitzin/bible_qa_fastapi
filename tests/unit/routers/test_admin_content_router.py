"""Tests for admin content router (question/answer deletion)."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_admin_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_override():
    async def mock_admin():
        return {"id": 1, "email": "admin@example.com", "is_admin": True}

    app.dependency_overrides[get_current_admin_user] = mock_admin
    yield
    app.dependency_overrides.clear()


class TestAdminDeleteQuestion:

    @patch("app.routers.admin_content.QuestionRepository.delete_question")
    def test_delete_question_success(self, mock_delete):
        mock_delete.return_value = True

        response = client.delete("/api/admin/questions/42")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["question_id"] == 42

    @patch("app.routers.admin_content.QuestionRepository.delete_question")
    def test_delete_question_not_found(self, mock_delete):
        mock_delete.return_value = False

        response = client.delete("/api/admin/questions/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.routers.admin_content.QuestionRepository.delete_question")
    def test_delete_question_db_error(self, mock_delete):
        mock_delete.side_effect = Exception("DB error")

        response = client.delete("/api/admin/questions/1")

        assert response.status_code == 500


class TestAdminDeleteSavedAnswer:

    @patch("app.routers.admin_content.SavedAnswersRepository.admin_delete_saved_answer")
    def test_delete_saved_answer_success(self, mock_delete):
        mock_delete.return_value = True

        response = client.delete("/api/admin/saved_answers/10")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["answer_id"] == 10

    @patch("app.routers.admin_content.SavedAnswersRepository.admin_delete_saved_answer")
    def test_delete_saved_answer_not_found(self, mock_delete):
        mock_delete.return_value = False

        response = client.delete("/api/admin/saved_answers/999")

        assert response.status_code == 404

    @patch("app.routers.admin_content.SavedAnswersRepository.admin_delete_saved_answer")
    def test_delete_saved_answer_db_error(self, mock_delete):
        mock_delete.side_effect = Exception("DB error")

        response = client.delete("/api/admin/saved_answers/1")

        assert response.status_code == 500
