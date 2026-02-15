"""Tests for admin user management endpoints."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_admin_user

client = TestClient(app)


@pytest.fixture
def mock_admin_user():
    """Mock admin user for authentication."""
    def override_get_admin():
        return {"id": 1, "email": "admin@example.com", "is_admin": True}
    
    app.dependency_overrides[get_current_admin_user] = override_get_admin
    yield
    app.dependency_overrides.pop(get_current_admin_user, None)


class TestListUsers:
    """Tests for GET /api/admin/users/"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_list_users_success(self, mock_get_db, mock_admin_user):
        """Test successfully listing users."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "email": "user1@example.com",
                "username": "user1",
                "is_active": True,
                "is_admin": False,
                "created_at": datetime(2025, 1, 1, 12, 0, 0),
                "question_count": 5,
                "saved_answer_count": 2,
                "last_activity": datetime(2025, 1, 15, 10, 30, 0),
            },
            {
                "id": 2,
                "email": "user2@example.com",
                "username": "user2",
                "is_active": True,
                "is_admin": False,
                "created_at": datetime(2025, 1, 2, 14, 0, 0),
                "question_count": 0,
                "saved_answer_count": 0,
                "last_activity": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["email"] == "user1@example.com"
        assert data[0]["question_count"] == 5
        assert data[1]["email"] == "user2@example.com"
        assert data[1]["last_activity"] is None

    @patch('app.routers.admin_users.get_db_connection')
    def test_list_users_with_search(self, mock_get_db, mock_admin_user):
        """Test listing users with search filter."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "email": "john@example.com",
                "username": "john",
                "is_active": True,
                "is_admin": False,
                "created_at": datetime(2025, 1, 1),
                "question_count": 3,
                "saved_answer_count": 1,
                "last_activity": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/?search=john")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == "john@example.com"
        # Verify search parameter was used in query
        call_args = mock_cursor.execute.call_args[0]
        assert "ILIKE" in call_args[0]

    @patch('app.routers.admin_users.get_db_connection')
    def test_list_users_active_only(self, mock_get_db, mock_admin_user):
        """Test listing only active users."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/?active_only=true")

        assert response.status_code == 200
        # Verify active filter was used
        call_args = mock_cursor.execute.call_args[0]
        assert "is_active = true" in call_args[0]

    @patch('app.routers.admin_users.get_db_connection')
    def test_list_users_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB connection failed")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.get("/api/admin/users/")

        assert response.status_code == 500
        assert "Failed to list users" in response.json()["detail"]

    def test_list_users_requires_admin(self):
        """Test that non-admin users cannot list users."""
        response = client.get("/api/admin/users/")
        assert response.status_code == 401


class TestGetUserStats:
    """Tests for GET /api/admin/users/stats"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_stats_success(self, mock_get_db, mock_admin_user):
        """Test successfully getting user statistics."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            {
                "total_users": 100,
                "active_users": 85,
                "admin_users": 2,
                "guest_users": 13,
            },
            {
                "users_with_questions": 45,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 100
        assert data["active_users"] == 85
        assert data["admin_users"] == 2
        assert data["guest_users"] == 13
        assert data["users_with_questions"] == 45

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_stats_handles_null_values(self, mock_get_db, mock_admin_user):
        """Test that null values are handled correctly."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            {
                "total_users": None,
                "active_users": None,
                "admin_users": None,
                "guest_users": None,
            },
            {
                "users_with_questions": None,
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 0
        assert data["active_users"] == 0
        assert data["admin_users"] == 0
        assert data["users_with_questions"] == 0

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_stats_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB connection failed")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.get("/api/admin/users/stats")

        assert response.status_code == 500
        assert "Failed to get user stats" in response.json()["detail"]

    def test_get_user_stats_requires_admin(self):
        """Test that non-admin users cannot get stats."""
        response = client.get("/api/admin/users/stats")
        assert response.status_code == 401


class TestGetUserDetail:
    """Tests for GET /api/admin/users/{user_id}"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_detail_success(self, mock_get_db, mock_admin_user):
        """Test successfully getting user details."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": 5,
            "email": "user@example.com",
            "username": "testuser",
            "is_active": True,
            "is_admin": False,
            "created_at": datetime(2025, 1, 1, 12, 0, 0),
            "question_count": 10,
            "saved_answer_count": 5,
            "recent_question_count": 3,
            "last_activity": datetime(2025, 1, 20, 15, 30, 0),
        }
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/5")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 5
        assert data["email"] == "user@example.com"
        assert data["question_count"] == 10
        assert data["saved_answer_count"] == 5
        assert data["recent_question_count"] == 3
        assert data["last_activity"] is not None

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_detail_not_found(self, mock_get_db, mock_admin_user):
        """Test getting details for non-existent user."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.get("/api/admin/users/999")

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_get_user_detail_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB connection failed")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.get("/api/admin/users/5")

        assert response.status_code == 500
        assert "Failed to get user detail" in response.json()["detail"]

    def test_get_user_detail_requires_admin(self):
        """Test that non-admin users cannot get user details."""
        response = client.get("/api/admin/users/1")
        assert response.status_code == 401


class TestResetUserAccount:
    """Tests for POST /api/admin/users/{user_id}/reset-account"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_reset_user_account_success(self, mock_get_db, mock_admin_user):
        """Test successfully resetting a user account clears all data."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5}
        # Simulate rowcount for each DELETE statement
        mock_cursor.rowcount = 0
        type(mock_cursor).rowcount = Mock(side_effect=[3, 2, 1, 0, 1])
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/5/reset-account")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "deleted" in data
        assert "questions" in data["deleted"]
        assert "saved_answers" in data["deleted"]
        assert "recent_questions" in data["deleted"]
        assert "notes" in data["deleted"]
        assert "reading_plans" in data["deleted"]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_reset_user_account_not_found(self, mock_get_db, mock_admin_user):
        """Test resetting a non-existent user returns 404."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/999/reset-account")

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_reset_user_account_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB error")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.post("/api/admin/users/5/reset-account")

        assert response.status_code == 500
        assert "Failed to reset user account" in response.json()["detail"]


class TestClearSavedAnswers:
    """Tests for POST /api/admin/users/{user_id}/clear-saved-answers"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_clear_saved_answers_success(self, mock_get_db, mock_admin_user):
        """Test successfully clearing saved answers returns deleted count."""
        mock_cursor = MagicMock()
        # First fetchone for user existence check
        mock_cursor.fetchone.return_value = {"id": 5}
        mock_cursor.rowcount = 7
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/5/clear-saved-answers")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 7
        assert "Cleared 7 saved answer(s)" in data["message"]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_clear_saved_answers_not_found(self, mock_get_db, mock_admin_user):
        """Test clearing saved answers for non-existent user returns 404."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/999/clear-saved-answers")

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_clear_saved_answers_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB error")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.post("/api/admin/users/5/clear-saved-answers")

        assert response.status_code == 500
        assert "Failed to clear saved answers" in response.json()["detail"]


class TestToggleUserActive:
    """Tests for POST /api/admin/users/{user_id}/toggle-active"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_toggle_active_to_inactive(self, mock_get_db, mock_admin_user):
        """Test toggling an active user to inactive."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"is_active": True}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/5/toggle-active")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_active"] is False
        assert "deactivated" in data["message"]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_toggle_inactive_to_active(self, mock_get_db, mock_admin_user):
        """Test toggling an inactive user to active."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"is_active": False}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/5/toggle-active")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_active"] is True
        assert "activated" in data["message"]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_toggle_active_user_not_found(self, mock_get_db, mock_admin_user):
        """Test toggling a non-existent user returns 404."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/999/toggle-active")

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_toggle_active_cannot_disable_self(self, mock_get_db, mock_admin_user):
        """Test that admin cannot disable their own account (admin id=1)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"is_active": True}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/1/toggle-active")

        assert response.status_code == 400
        assert "Cannot disable your own account" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_toggle_active_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB error")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.post("/api/admin/users/5/toggle-active")

        assert response.status_code == 500
        assert "Failed to toggle user active status" in response.json()["detail"]


class TestDeleteUser:
    """Tests for DELETE /api/admin/users/{user_id}"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_delete_user_success(self, mock_get_db, mock_admin_user):
        """Test successfully deleting a user."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5, "email": "user@example.com"}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.delete("/api/admin/users/5")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "permanently deleted" in data["message"]
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_delete_user_not_found(self, mock_get_db, mock_admin_user):
        """Test deleting a non-existent user returns 404."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.delete("/api/admin/users/999")

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_delete_user_cannot_delete_self(self, mock_get_db, mock_admin_user):
        """Test that admin cannot delete their own account (admin id=1)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "email": "admin@example.com"}
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.delete("/api/admin/users/1")

        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_delete_user_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB error")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.delete("/api/admin/users/5")

        assert response.status_code == 500
        assert "Failed to delete user" in response.json()["detail"]


class TestCleanupGuestUsers:
    """Tests for POST /api/admin/users/cleanup-guest-users"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_cleanup_guest_users_success(self, mock_get_db, mock_admin_user):
        """Test successfully cleaning up guest users."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 10, "username": "guest_10"},
            {"id": 11, "username": "guest_11"},
            {"id": 12, "username": "guest_12"},
        ]
        mock_cursor.rowcount = 3
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/cleanup-guest-users")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 3
        assert "Cleaned up 3 guest user(s)" in data["message"]
        assert len(data["deleted_users"]) == 3
        mock_conn.commit.assert_called_once()

    @patch('app.routers.admin_users.get_db_connection')
    def test_cleanup_guest_users_none_found(self, mock_get_db, mock_admin_user):
        """Test cleanup when no guest users exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/cleanup-guest-users")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 0
        assert "No guest users to clean up" in data["message"]

    @patch('app.routers.admin_users.get_db_connection')
    def test_cleanup_guest_users_db_error(self, mock_get_db, mock_admin_user):
        """Test that database errors return 500."""
        mock_get_db.return_value.__enter__.side_effect = Exception("DB error")
        mock_get_db.return_value.__exit__ = Mock(return_value=None)

        response = client.post("/api/admin/users/cleanup-guest-users")

        assert response.status_code == 500
        assert "Failed to cleanup guest users" in response.json()["detail"]
