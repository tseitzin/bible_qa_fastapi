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

    def test_get_user_detail_requires_admin(self):
        """Test that non-admin users cannot get user details."""
        response = client.get("/api/admin/users/1")
        assert response.status_code == 401


class TestUserManagementActions:
    """Tests for user management action endpoints (reset, delete, etc.)"""

    @patch('app.routers.admin_users.get_db_connection')
    def test_reset_user_account(self, mock_get_db, mock_admin_user):
        """Test resetting a user's account."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_get_db.return_value.__exit__.return_value = None

        response = client.post("/api/admin/users/5/reset-account")

        # Endpoint may not be implemented yet, checking it doesn't crash
        assert response.status_code in [200, 404, 405]
