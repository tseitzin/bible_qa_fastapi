"""Tests for the authentication router."""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestRegister:

    @patch("app.routers.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.routers.auth.create_user")
    @patch("app.routers.auth.get_user_by_email")
    def test_register_success(self, mock_get_user, mock_create, mock_ip):
        mock_get_user.return_value = None
        mock_create.return_value = {
            "id": 1, "email": "new@example.com", "username": "newuser",
            "is_active": True, "is_admin": False,
            "created_at": "2025-01-01T00:00:00",
        }

        response = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "securepassword123",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"

    @patch("app.routers.auth.get_user_by_email")
    def test_register_duplicate_email(self, mock_get_user):
        mock_get_user.return_value = {"id": 1, "email": "exists@example.com"}

        response = client.post("/api/auth/register", json={
            "email": "exists@example.com",
            "username": "user",
            "password": "securepassword123",
        })

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_register_invalid_email(self):
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "username": "user",
            "password": "securepassword123",
        })

        assert response.status_code == 422

    def test_register_short_password(self):
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "user",
            "password": "short",
        })

        assert response.status_code == 422


class TestLogin:

    @patch("app.routers.auth.set_csrf_cookie")
    @patch("app.routers.auth.generate_csrf_token", return_value="csrf-tok")
    @patch("app.routers.auth.set_auth_cookie")
    @patch("app.routers.auth.create_access_token", return_value="jwt-token")
    @patch("app.routers.auth.update_user_ip_address")
    @patch("app.routers.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.routers.auth.get_user_by_id")
    @patch("app.routers.auth.verify_password")
    @patch("app.routers.auth.get_user_by_email")
    def test_login_success(
        self, mock_get_user, mock_verify, mock_get_by_id,
        mock_ip, mock_update_ip, mock_token, mock_set_auth,
        mock_csrf_token, mock_set_csrf,
    ):
        mock_get_user.return_value = {
            "id": 1, "email": "test@example.com", "username": "testuser",
            "hashed_password": "hashed", "is_active": True, "is_admin": False,
            "created_at": "2025-01-01T00:00:00",
        }
        mock_verify.return_value = True
        mock_get_by_id.return_value = {
            "id": 1, "email": "test@example.com", "username": "testuser",
            "is_active": True, "is_admin": False,
            "created_at": "2025-01-01T00:00:00",
        }

        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        mock_set_auth.assert_called_once()

    @patch("app.routers.auth.verify_password")
    @patch("app.routers.auth.get_user_by_email")
    def test_login_wrong_password(self, mock_get_user, mock_verify):
        mock_get_user.return_value = {
            "id": 1, "hashed_password": "hashed", "is_active": True,
        }
        mock_verify.return_value = False

        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrong",
        })

        assert response.status_code == 401

    @patch("app.routers.auth.get_user_by_email")
    def test_login_user_not_found(self, mock_get_user):
        mock_get_user.return_value = None

        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123",
        })

        assert response.status_code == 401

    @patch("app.routers.auth.verify_password")
    @patch("app.routers.auth.get_user_by_email")
    def test_login_inactive_user(self, mock_get_user, mock_verify):
        mock_get_user.return_value = {
            "id": 1, "hashed_password": "hashed", "is_active": False,
        }
        mock_verify.return_value = True

        response = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })

        assert response.status_code == 400
        assert "Inactive" in response.json()["detail"]


class TestLogout:

    @patch("app.routers.auth.clear_csrf_cookie")
    @patch("app.routers.auth.clear_auth_cookie")
    def test_logout(self, mock_clear_auth, mock_clear_csrf):
        response = client.post("/api/auth/logout")

        assert response.status_code == 204
        mock_clear_auth.assert_called_once()
        mock_clear_csrf.assert_called_once()


class TestGetCurrentUser:

    @patch("app.routers.auth.get_current_user")
    def test_get_me_authenticated(self, mock_get_user):
        mock_get_user.return_value = {
            "id": 1, "email": "test@example.com", "username": "testuser",
            "is_active": True, "is_admin": False,
            "created_at": "2025-01-01T00:00:00",
        }

        response = client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
