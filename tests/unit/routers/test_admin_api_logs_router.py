"""Tests for admin API logs router."""
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_admin_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def admin_override():
    """Override admin auth for all tests."""
    async def mock_admin():
        return {"id": 1, "email": "admin@example.com", "is_admin": True}

    app.dependency_overrides[get_current_admin_user] = mock_admin
    yield
    app.dependency_overrides.clear()


class TestGetApiLogs:

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_logs")
    def test_get_logs_basic(self, mock_get_logs):
        mock_get_logs.return_value = [{"id": 1, "endpoint": "/api/ask"}]

        response = client.get("/api/admin/logs/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["logs"]) == 1

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_logs")
    def test_get_logs_with_filters(self, mock_get_logs):
        mock_get_logs.return_value = []

        response = client.get("/api/admin/logs/", params={
            "user_id": 1, "endpoint": "/api/ask", "status_code": 200,
            "limit": 50, "offset": 10,
        })

        assert response.status_code == 200
        mock_get_logs.assert_called_once_with(
            limit=50, offset=10, user_id=1, endpoint="/api/ask",
            status_code=200, start_date=None, end_date=None,
        )

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_logs")
    def test_get_logs_handles_error(self, mock_get_logs):
        mock_get_logs.side_effect = Exception("DB down")

        response = client.get("/api/admin/logs/")

        assert response.status_code == 500


class TestGetApiStats:

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_stats")
    def test_get_stats(self, mock_get_stats):
        mock_get_stats.return_value = {
            "total_requests": 100, "unique_users": 10,
            "successful_requests": 90, "error_requests": 10,
            "openai_requests": 50,
        }

        response = client.get("/api/admin/logs/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 100

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_stats")
    def test_get_stats_empty(self, mock_get_stats):
        mock_get_stats.return_value = None

        response = client.get("/api/admin/logs/stats")

        assert response.status_code == 200
        assert response.json()["total_requests"] == 0


class TestGetEndpointStats:

    @patch("app.routers.admin_api_logs.ApiRequestLogRepository.get_endpoint_stats")
    def test_get_endpoint_stats(self, mock_get_stats):
        mock_get_stats.return_value = [
            {"endpoint": "/api/ask", "request_count": 50, "success_rate": 95.0},
        ]

        response = client.get("/api/admin/logs/endpoints")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


class TestGetOpenAICalls:

    @patch("app.routers.admin_api_logs.OpenAIApiCallRepository.get_calls")
    def test_get_openai_calls(self, mock_get_calls):
        mock_get_calls.return_value = [{"id": 1, "question": "Q?"}]

        response = client.get("/api/admin/logs/openai")

        assert response.status_code == 200
        assert response.json()["count"] == 1


class TestGetOpenAIStats:

    @patch("app.routers.admin_api_logs.OpenAIApiCallRepository.get_usage_stats")
    def test_get_openai_stats(self, mock_get_stats):
        mock_get_stats.return_value = {
            "total_calls": 50, "unique_users": 5,
            "total_tokens_used": 10000, "total_prompt_tokens": 4000,
            "total_completion_tokens": 6000, "avg_tokens_per_call": 200.0,
            "avg_response_time_ms": 1500.0, "successful_calls": 45,
            "error_calls": 3, "rate_limit_calls": 2,
        }

        response = client.get("/api/admin/logs/openai/stats")

        assert response.status_code == 200
        assert response.json()["total_calls"] == 50


class TestGetOpenAIUserUsage:

    @patch("app.routers.admin_api_logs.OpenAIApiCallRepository.get_user_usage")
    def test_get_user_usage(self, mock_get_usage):
        mock_get_usage.return_value = [
            {"user_id": 1, "call_count": 10},
        ]

        response = client.get("/api/admin/logs/openai/users")

        assert response.status_code == 200
        assert response.json()["count"] == 1
