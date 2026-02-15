"""Tests for page analytics router."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user_optional_dependency, get_current_admin_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def auth_user():
    app.dependency_overrides[get_current_user_optional_dependency] = lambda: {
        "id": 1,
        "email": "user@example.com",
    }
    yield


@pytest.fixture
def anon_user():
    app.dependency_overrides[get_current_user_optional_dependency] = lambda: None
    yield


@pytest.fixture
def admin_user():
    app.dependency_overrides[get_current_admin_user] = lambda: {
        "id": 1,
        "email": "admin@example.com",
        "is_admin": True,
    }
    app.dependency_overrides[get_current_user_optional_dependency] = lambda: {
        "id": 1,
        "email": "admin@example.com",
        "is_admin": True,
    }
    yield


class TestLogPageView:
    """Tests for POST /api/analytics/page-view."""

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="127.0.0.1")
    def test_success_authenticated(self, mock_ip, mock_log, mock_geo, auth_user):
        mock_geo.return_value = None
        mock_log.return_value = 42

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_title": "Home",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["page_analytics_id"] == 42
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["session_id"] == "abc123"
        assert call_kwargs["page_path"] == "/home"
        assert call_kwargs["page_title"] == "Home"
        assert call_kwargs["ip_address"] == "127.0.0.1"

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="127.0.0.1")
    def test_success_anonymous(self, mock_ip, mock_log, mock_geo, anon_user):
        mock_geo.return_value = None
        mock_log.return_value = 43

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "anon-session",
                "page_path": "/about",
            },
        )

        assert response.status_code == 200
        assert response.json()["page_analytics_id"] == 43
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] is None

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="127.0.0.1")
    def test_with_referrer(self, mock_ip, mock_log, mock_geo, auth_user):
        mock_geo.return_value = None
        mock_log.return_value = 44

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_title": "Home",
                "referrer": "https://google.com",
            },
        )

        assert response.status_code == 200
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["referrer"] == "https://google.com"

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="73.162.55.100")
    def test_with_geolocation(self, mock_ip, mock_log, mock_geo, auth_user):
        mock_geo.return_value = {
            "country_code": "US",
            "country_name": "United States",
            "city": "New York",
        }
        mock_log.return_value = 45

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_title": "Home",
            },
        )

        assert response.status_code == 200
        # Router calls lookup_ip with mocked IP; middleware may also call it
        mock_geo.assert_any_call("73.162.55.100")
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["country_code"] == "US"
        assert call_kwargs["country_name"] == "United States"
        assert call_kwargs["city"] == "New York"

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="10.0.0.1")
    def test_skips_geolocation_for_private_ip(
        self, mock_ip, mock_log, mock_geo, auth_user
    ):
        mock_log.return_value = 46

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_title": "Home",
            },
        )

        assert response.status_code == 200
        # Router skips geolocation for private IPs; middleware may still call it
        ip_calls = [c.args[0] for c in mock_geo.call_args_list]
        assert "10.0.0.1" not in ip_calls
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["country_code"] is None
        assert call_kwargs["country_name"] is None
        assert call_kwargs["city"] is None

    @patch(
        "app.routers.page_analytics.GeolocationService.lookup_ip",
        new_callable=AsyncMock,
    )
    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="73.162.55.100")
    def test_geolocation_failure_is_non_fatal(
        self, mock_ip, mock_log, mock_geo, auth_user
    ):
        mock_geo.side_effect = Exception("Geo service down")
        mock_log.return_value = 47

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_title": "Home",
            },
        )

        assert response.status_code == 200
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["country_code"] is None

    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_page_view")
    @patch("app.routers.page_analytics.get_client_ip", return_value="127.0.0.1")
    def test_db_error_returns_500(self, mock_ip, mock_log, anon_user):
        mock_log.side_effect = Exception("DB error")

        response = client.post(
            "/api/analytics/page-view",
            json={
                "session_id": "abc123",
                "page_path": "/home",
            },
        )

        assert response.status_code == 500
        assert "Failed to log page view" in response.json()["detail"]


class TestUpdatePageMetrics:
    """Tests for PUT /api/analytics/page-metrics."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.update_page_metrics")
    def test_success_full_update(self, mock_update):
        response = client.put(
            "/api/analytics/page-metrics",
            json={
                "page_analytics_id": 1,
                "visit_duration_seconds": 120,
                "max_scroll_depth_percent": 75,
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_update.assert_called_once_with(
            page_analytics_id=1,
            visit_duration_seconds=120,
            max_scroll_depth_percent=75,
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.update_page_metrics")
    def test_success_partial_update_duration_only(self, mock_update):
        response = client.put(
            "/api/analytics/page-metrics",
            json={
                "page_analytics_id": 5,
                "visit_duration_seconds": 60,
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_update.assert_called_once_with(
            page_analytics_id=5,
            visit_duration_seconds=60,
            max_scroll_depth_percent=None,
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.update_page_metrics")
    def test_success_partial_update_scroll_only(self, mock_update):
        response = client.put(
            "/api/analytics/page-metrics",
            json={
                "page_analytics_id": 5,
                "max_scroll_depth_percent": 90,
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_update.assert_called_once_with(
            page_analytics_id=5,
            visit_duration_seconds=None,
            max_scroll_depth_percent=90,
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.update_page_metrics")
    def test_db_error_returns_500(self, mock_update):
        mock_update.side_effect = Exception("DB error")

        response = client.put(
            "/api/analytics/page-metrics",
            json={
                "page_analytics_id": 1,
                "visit_duration_seconds": 120,
            },
        )

        assert response.status_code == 500
        assert "Failed to update page metrics" in response.json()["detail"]


class TestLogClickEvent:
    """Tests for POST /api/analytics/click-event."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_click_event")
    def test_success_authenticated(self, mock_log, auth_user):
        mock_log.return_value = 10

        response = client.post(
            "/api/analytics/click-event",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "element_type": "button",
                "element_id": "submit-btn",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["click_event_id"] == 10
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["element_type"] == "button"
        assert call_kwargs["element_id"] == "submit-btn"

    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_click_event")
    def test_success_anonymous(self, mock_log, anon_user):
        mock_log.return_value = 11

        response = client.post(
            "/api/analytics/click-event",
            json={
                "session_id": "anon-session",
                "page_path": "/about",
                "element_type": "link",
            },
        )

        assert response.status_code == 200
        assert response.json()["click_event_id"] == 11
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["user_id"] is None

    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_click_event")
    def test_success_with_all_optional_fields(self, mock_log, auth_user):
        mock_log.return_value = 12

        response = client.post(
            "/api/analytics/click-event",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "page_analytics_id": 42,
                "element_type": "button",
                "element_id": "cta-btn",
                "element_text": "Sign Up",
                "element_class": "btn-primary",
                "click_position_x": 150,
                "click_position_y": 300,
            },
        )

        assert response.status_code == 200
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["page_analytics_id"] == 42
        assert call_kwargs["element_text"] == "Sign Up"
        assert call_kwargs["element_class"] == "btn-primary"
        assert call_kwargs["click_position_x"] == 150
        assert call_kwargs["click_position_y"] == 300

    @patch("app.routers.page_analytics.PageAnalyticsRepository.log_click_event")
    def test_db_error_returns_500(self, mock_log, auth_user):
        mock_log.side_effect = Exception("DB error")

        response = client.post(
            "/api/analytics/click-event",
            json={
                "session_id": "abc123",
                "page_path": "/home",
                "element_type": "button",
            },
        )

        assert response.status_code == 500
        assert "Failed to log click event" in response.json()["detail"]


class TestGetPageAnalyticsStats:
    """Tests for GET /api/analytics/admin/stats."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_analytics_stats")
    def test_success(self, mock_stats, admin_user):
        mock_stats.return_value = {
            "total_page_views": 100,
            "unique_sessions": 50,
            "avg_duration": 45.2,
        }

        response = client.get("/api/analytics/admin/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_page_views"] == 100
        assert data["unique_sessions"] == 50
        mock_stats.assert_called_once_with(start_date=None, end_date=None)

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_analytics_stats")
    def test_success_with_date_filters(self, mock_stats, admin_user):
        mock_stats.return_value = {"total_page_views": 25}

        response = client.get(
            "/api/analytics/admin/stats",
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )

        assert response.status_code == 200
        mock_stats.assert_called_once_with(
            start_date="2026-01-01", end_date="2026-01-31"
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_analytics_stats")
    def test_db_error_returns_500(self, mock_stats, admin_user):
        mock_stats.side_effect = Exception("DB error")

        response = client.get("/api/analytics/admin/stats")

        assert response.status_code == 500
        assert "Failed to get analytics stats" in response.json()["detail"]

    def test_non_admin_returns_error(self):
        """Non-admin users should not access admin stats."""
        response = client.get("/api/analytics/admin/stats")
        assert response.status_code in (401, 403)


class TestGetPageViews:
    """Tests for GET /api/analytics/admin/page-views."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_views")
    def test_success(self, mock_views, admin_user):
        mock_views.return_value = [
            {"id": 1, "page_path": "/home", "session_id": "s1"},
            {"id": 2, "page_path": "/about", "session_id": "s2"},
        ]

        response = client.get("/api/analytics/admin/page-views")

        assert response.status_code == 200
        data = response.json()
        assert len(data["page_views"]) == 2
        mock_views.assert_called_once_with(
            limit=100,
            offset=0,
            user_id=None,
            page_path=None,
            start_date=None,
            end_date=None,
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_views")
    def test_success_with_filters(self, mock_views, admin_user):
        mock_views.return_value = [{"id": 1, "page_path": "/home"}]

        response = client.get(
            "/api/analytics/admin/page-views",
            params={
                "limit": 10,
                "offset": 5,
                "user_id": 3,
                "page_path": "/home",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )

        assert response.status_code == 200
        mock_views.assert_called_once_with(
            limit=10,
            offset=5,
            user_id=3,
            page_path="/home",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_views")
    def test_db_error_returns_500(self, mock_views, admin_user):
        mock_views.side_effect = Exception("DB error")

        response = client.get("/api/analytics/admin/page-views")

        assert response.status_code == 500
        assert "Failed to get page views" in response.json()["detail"]

    def test_non_admin_returns_error(self):
        response = client.get("/api/analytics/admin/page-views")
        assert response.status_code in (401, 403)


class TestGetPagePathStats:
    """Tests for GET /api/analytics/admin/page-path-stats."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_path_stats")
    def test_success(self, mock_stats, admin_user):
        mock_stats.return_value = [
            {"page_path": "/home", "view_count": 50},
            {"page_path": "/about", "view_count": 30},
        ]

        response = client.get("/api/analytics/admin/page-path-stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data["page_stats"]) == 2
        assert data["page_stats"][0]["view_count"] == 50
        mock_stats.assert_called_once_with(
            limit=20, start_date=None, end_date=None
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_path_stats")
    def test_success_with_filters(self, mock_stats, admin_user):
        mock_stats.return_value = []

        response = client.get(
            "/api/analytics/admin/page-path-stats",
            params={
                "limit": 5,
                "start_date": "2026-02-01",
                "end_date": "2026-02-14",
            },
        )

        assert response.status_code == 200
        mock_stats.assert_called_once_with(
            limit=5, start_date="2026-02-01", end_date="2026-02-14"
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_page_path_stats")
    def test_db_error_returns_500(self, mock_stats, admin_user):
        mock_stats.side_effect = Exception("DB error")

        response = client.get("/api/analytics/admin/page-path-stats")

        assert response.status_code == 500
        assert "Failed to get page path stats" in response.json()["detail"]

    def test_non_admin_returns_error(self):
        response = client.get("/api/analytics/admin/page-path-stats")
        assert response.status_code in (401, 403)


class TestGetClickEvents:
    """Tests for GET /api/analytics/admin/click-events."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_events")
    def test_success(self, mock_clicks, admin_user):
        mock_clicks.return_value = [
            {"id": 1, "element_type": "button", "page_path": "/home"},
        ]

        response = client.get("/api/analytics/admin/click-events")

        assert response.status_code == 200
        data = response.json()
        assert len(data["clicks"]) == 1
        mock_clicks.assert_called_once_with(
            limit=100,
            offset=0,
            page_analytics_id=None,
            user_id=None,
            page_path=None,
            element_type=None,
            start_date=None,
            end_date=None,
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_events")
    def test_success_with_filters(self, mock_clicks, admin_user):
        mock_clicks.return_value = []

        response = client.get(
            "/api/analytics/admin/click-events",
            params={
                "limit": 50,
                "offset": 10,
                "page_analytics_id": 7,
                "user_id": 2,
                "page_path": "/home",
                "element_type": "button",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )

        assert response.status_code == 200
        mock_clicks.assert_called_once_with(
            limit=50,
            offset=10,
            page_analytics_id=7,
            user_id=2,
            page_path="/home",
            element_type="button",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_events")
    def test_db_error_returns_500(self, mock_clicks, admin_user):
        mock_clicks.side_effect = Exception("DB error")

        response = client.get("/api/analytics/admin/click-events")

        assert response.status_code == 500
        assert "Failed to get click events" in response.json()["detail"]

    def test_non_admin_returns_error(self):
        response = client.get("/api/analytics/admin/click-events")
        assert response.status_code in (401, 403)


class TestGetClickStats:
    """Tests for GET /api/analytics/admin/click-stats."""

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_stats")
    def test_success(self, mock_stats, admin_user):
        mock_stats.return_value = [
            {"element_type": "button", "click_count": 30},
            {"element_type": "link", "click_count": 20},
        ]

        response = client.get("/api/analytics/admin/click-stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data["click_stats"]) == 2
        assert data["click_stats"][0]["click_count"] == 30
        mock_stats.assert_called_once_with(start_date=None, end_date=None)

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_stats")
    def test_success_with_date_filters(self, mock_stats, admin_user):
        mock_stats.return_value = [{"element_type": "button", "click_count": 5}]

        response = client.get(
            "/api/analytics/admin/click-stats",
            params={"start_date": "2026-02-01", "end_date": "2026-02-14"},
        )

        assert response.status_code == 200
        mock_stats.assert_called_once_with(
            start_date="2026-02-01", end_date="2026-02-14"
        )

    @patch("app.routers.page_analytics.PageAnalyticsRepository.get_click_stats")
    def test_db_error_returns_500(self, mock_stats, admin_user):
        mock_stats.side_effect = Exception("DB error")

        response = client.get("/api/analytics/admin/click-stats")

        assert response.status_code == 500
        assert "Failed to get click stats" in response.json()["detail"]

    def test_non_admin_returns_error(self):
        response = client.get("/api/analytics/admin/click-stats")
        assert response.status_code in (401, 403)
