"""Tests for the API request logging middleware."""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.middleware.api_request_logging import ApiRequestLoggingMiddleware


@pytest.fixture
def call_next():
    """Mock call_next returning a 200 response."""
    mock_response = Mock(status_code=200)
    return AsyncMock(return_value=mock_response)


def _make_request(method="GET", path="/api/health", user=None, headers=None, client_host="127.0.0.1"):
    """Build a mock request."""
    request = Mock()
    request.method = method
    request.url = Mock(path=path)
    request.headers = headers or {}
    request.client = Mock(host=client_host)
    request.state = Mock()
    if user:
        request.state.user = user
    else:
        # hasattr check should return False when no user
        del request.state.user
    return request


class TestApiRequestLoggingMiddleware:
    """Tests for ApiRequestLoggingMiddleware."""

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_logs_basic_request(self, mock_log, mock_geo, call_next):
        """Should log a basic GET request."""
        mock_geo.return_value = None
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request()
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args.kwargs["endpoint"] == "/api/health"
        assert call_args.kwargs["method"] == "GET"
        assert call_args.kwargs["status_code"] == 200

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_extracts_user_id_from_state(self, mock_log, mock_geo, call_next):
        """Should extract user_id from request.state.user when present."""
        mock_geo.return_value = None
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request(user={"id": 42, "email": "test@example.com"})
        await middleware.dispatch(request, call_next)

        call_args = mock_log.call_args
        assert call_args.kwargs["user_id"] == 42

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_includes_geolocation(self, mock_log, mock_geo, call_next):
        """Should include geolocation data when available."""
        mock_geo.return_value = {
            "country_code": "US",
            "country_name": "United States",
            "city": "San Francisco",
        }
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request(client_host="203.0.113.50")
        await middleware.dispatch(request, call_next)

        call_args = mock_log.call_args
        assert call_args.kwargs["country_code"] == "US"
        assert call_args.kwargs["country_name"] == "United States"
        assert call_args.kwargs["city"] == "San Francisco"

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_skips_geolocation_for_private_ips(self, mock_log, mock_geo, call_next):
        """Should skip geolocation lookup for private IPs starting with 10."""
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request(client_host="10.0.0.5")
        await middleware.dispatch(request, call_next)

        mock_geo.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_captures_payload_summary_for_post(self, mock_log, mock_geo, call_next):
        """Should capture content-type for POST requests."""
        mock_geo.return_value = None
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request(
            method="POST",
            path="/api/ask",
            headers={"content-type": "application/json"},
        )
        await middleware.dispatch(request, call_next)

        call_args = mock_log.call_args
        assert call_args.kwargs["payload_summary"] is not None
        assert "application/json" in call_args.kwargs["payload_summary"]

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_still_returns_response_on_logging_failure(self, mock_log, mock_geo, call_next):
        """Should return the response even if logging fails."""
        mock_log.side_effect = Exception("DB down")
        mock_geo.return_value = None
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request()
        response = await middleware.dispatch(request, call_next)

        # Response should still be returned
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.middleware.api_request_logging.GeolocationService.lookup_ip", new_callable=AsyncMock)
    @patch("app.middleware.api_request_logging.ApiRequestLogRepository.log_request")
    async def test_handles_geolocation_failure(self, mock_log, mock_geo, call_next):
        """Should gracefully handle geolocation lookup failure."""
        mock_geo.side_effect = Exception("Geo API down")
        app = Mock()
        middleware = ApiRequestLoggingMiddleware(app)

        request = _make_request(client_host="203.0.113.50")
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_args = mock_log.call_args
        assert call_args.kwargs["country_code"] is None
