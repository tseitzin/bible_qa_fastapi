"""Tests for PageAnalyticsRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.page_analytics import PageAnalyticsRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestPageAnalyticsRepository:

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_log_page_view(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 42}

        result = PageAnalyticsRepository.log_page_view(
            user_id=1, session_id="abc", page_path="/home",
        )

        assert result == 42
        conn.commit.assert_called_once()

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_log_page_view_with_geolocation(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 1}

        PageAnalyticsRepository.log_page_view(
            user_id=1, session_id="abc", page_path="/home",
            country_code="US", country_name="United States", city="NYC",
        )

        call_params = cur.execute.call_args[0][1]
        assert "US" in call_params

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_update_page_metrics(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        PageAnalyticsRepository.update_page_metrics(
            page_analytics_id=1, visit_duration_seconds=120, max_scroll_depth_percent=75,
        )

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_update_page_metrics_no_updates(self, mock_get_conn):
        """Should return early when no metrics provided."""
        conn, cur = _setup_db(mock_get_conn)

        PageAnalyticsRepository.update_page_metrics(page_analytics_id=1)

        cur.execute.assert_not_called()

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_log_click_event(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 10}

        result = PageAnalyticsRepository.log_click_event(
            page_analytics_id=1, user_id=1, session_id="abc", page_path="/home",
            element_type="button",
        )

        assert result == 10
        # Should also update clicks_count on page_analytics
        assert cur.execute.call_count == 2
        conn.commit.assert_called_once()

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_log_click_event_without_page_analytics_id(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 10}

        PageAnalyticsRepository.log_click_event(
            page_analytics_id=None, user_id=1, session_id="abc", page_path="/home",
        )

        # Should NOT update clicks_count when page_analytics_id is None
        assert cur.execute.call_count == 1

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_get_page_views(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [{"id": 1, "page_path": "/home"}]

        result = PageAnalyticsRepository.get_page_views()

        assert len(result) == 1

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_get_page_analytics_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "total_page_views": 100, "unique_users": 20,
            "unique_sessions": 50, "unique_pages": 10,
            "avg_duration_seconds": 45.0, "avg_scroll_depth_percent": 60.0,
            "total_clicks": 200,
        }

        result = PageAnalyticsRepository.get_page_analytics_stats()

        assert result["total_page_views"] == 100

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_get_page_path_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"page_path": "/home", "view_count": 50},
        ]

        result = PageAnalyticsRepository.get_page_path_stats()

        assert len(result) == 1

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_get_click_events(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        result = PageAnalyticsRepository.get_click_events()

        assert result == []

    @patch("app.repositories.page_analytics.get_db_connection")
    def test_get_click_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"element_type": "button", "click_count": 30, "unique_users": 10, "pages_affected": 5},
        ]

        result = PageAnalyticsRepository.get_click_stats()

        assert len(result) == 1
        assert result[0]["element_type"] == "button"
