"""Tests for the CSRF middleware."""
import pytest
from unittest.mock import AsyncMock, Mock

from app.middleware.csrf import CSRFMiddleware


@pytest.fixture
def mock_settings():
    """Mock settings for CSRF middleware."""
    settings = Mock()
    settings.csrf_protection_enabled = True
    settings.csrf_exempt_paths = ["/api/auth/login", "/api/auth/register"]
    settings.auth_cookie_name = "bible_qa_auth"
    settings.csrf_cookie_name = "bible_qa_csrf"
    settings.csrf_header_name = "X-CSRF-Token"
    return settings


@pytest.fixture
def call_next():
    """Mock call_next that returns a 200 response."""
    mock_response = Mock(status_code=200)
    return AsyncMock(return_value=mock_response)


def _make_request(method="POST", path="/api/ask", cookies=None, headers=None):
    """Helper to build a mock request."""
    request = Mock()
    request.method = method
    request.url = Mock(path=path)
    request.cookies = cookies or {}
    request.headers = headers or {}
    return request


class TestCSRFMiddleware:
    """Tests for CSRFMiddleware dispatch."""

    @pytest.mark.asyncio
    async def test_passes_when_csrf_disabled(self, mock_settings, call_next):
        """Should pass all requests through when CSRF is disabled."""
        mock_settings.csrf_protection_enabled = False
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(method="POST")
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_passes_safe_methods(self, mock_settings, call_next):
        """GET, HEAD, OPTIONS, TRACE should always pass."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        for method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            request = _make_request(method=method)
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_passes_exempt_paths(self, mock_settings, call_next):
        """Exempt paths should be allowed without CSRF token."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(
            method="POST",
            path="/api/auth/login",
            cookies={"bible_qa_auth": "some-jwt"},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_passes_when_no_auth_cookie(self, mock_settings, call_next):
        """Without an auth cookie, there's nothing to protect."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(method="POST", cookies={})
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_missing_csrf_token(self, mock_settings, call_next):
        """Should return 403 when auth cookie present but no CSRF token."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(
            method="POST",
            cookies={"bible_qa_auth": "some-jwt"},
            headers={},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_mismatched_csrf_token(self, mock_settings, call_next):
        """Should return 403 when cookie and header tokens don't match."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(
            method="POST",
            cookies={"bible_qa_auth": "some-jwt", "bible_qa_csrf": "token-a"},
            headers={"X-CSRF-Token": "token-b"},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_passes_valid_csrf_token(self, mock_settings, call_next):
        """Should pass when cookie and header CSRF tokens match."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        token = "matching-csrf-token"
        request = _make_request(
            method="POST",
            cookies={"bible_qa_auth": "some-jwt", "bible_qa_csrf": token},
            headers={"X-CSRF-Token": token},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_missing_csrf_cookie_with_header(self, mock_settings, call_next):
        """Should reject when header is present but cookie is missing."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(
            method="POST",
            cookies={"bible_qa_auth": "some-jwt"},
            headers={"X-CSRF-Token": "some-token"},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_custom_exempt_paths(self, mock_settings, call_next):
        """Should respect custom exempt paths passed to constructor."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings, exempt_paths=["/api/webhooks"])

        request = _make_request(
            method="POST",
            path="/api/webhooks/stripe",
            cookies={"bible_qa_auth": "some-jwt"},
        )
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_case_insensitive_method(self, mock_settings, call_next):
        """Should handle mixed-case HTTP methods."""
        app = Mock()
        middleware = CSRFMiddleware(app, settings=mock_settings)

        request = _make_request(method="get")
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
