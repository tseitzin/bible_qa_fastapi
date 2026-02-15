"""Tests for ApiRequestLogRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.api_request_log import ApiRequestLogRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestApiRequestLogRepository:

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_log_request(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        ApiRequestLogRepository.log_request(
            user_id=1, endpoint="/api/ask", method="POST",
            status_code=200, ip_address="1.2.3.4",
        )

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_log_request_with_geolocation(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        ApiRequestLogRepository.log_request(
            user_id=1, endpoint="/api/ask", method="POST",
            status_code=200, country_code="US", country_name="United States", city="NYC",
        )

        call_args = cur.execute.call_args[0][1]
        assert "US" in call_args

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_log_request_handles_db_error(self, mock_get_conn):
        """Should not raise when database fails."""
        mock_get_conn.side_effect = Exception("DB down")

        # Should not raise
        ApiRequestLogRepository.log_request(
            user_id=1, endpoint="/api/ask", method="POST", status_code=200,
        )

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_get_logs_basic(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [{"id": 1, "endpoint": "/api/ask"}]

        result = ApiRequestLogRepository.get_logs()

        assert len(result) == 1

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_get_logs_with_filters(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        ApiRequestLogRepository.get_logs(
            user_id=1, endpoint="/api/ask", status_code=200,
            start_date="2025-01-01", end_date="2025-12-31",
        )

        sql = cur.execute.call_args[0][0]
        assert "user_id" in sql
        assert "endpoint" in sql
        assert "status_code" in sql

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_get_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "total_requests": 100, "unique_users": 10,
            "successful_requests": 90, "error_requests": 10,
            "openai_requests": 50,
        }

        result = ApiRequestLogRepository.get_stats()

        assert result["total_requests"] == 100

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_get_stats_empty(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = ApiRequestLogRepository.get_stats()

        assert result == {}

    @patch("app.repositories.api_request_log.get_db_connection")
    def test_get_endpoint_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"endpoint": "/api/ask", "request_count": 50, "success_rate": 95.0},
        ]

        result = ApiRequestLogRepository.get_endpoint_stats()

        assert len(result) == 1
        assert result[0]["endpoint"] == "/api/ask"
