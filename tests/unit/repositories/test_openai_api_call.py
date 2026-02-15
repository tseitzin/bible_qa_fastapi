"""Tests for OpenAIApiCallRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.openai_api_call import OpenAIApiCallRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestOpenAIApiCallRepository:

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_log_call(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        OpenAIApiCallRepository.log_call(
            user_id=1, question="What is faith?", model="gpt-4",
            prompt_tokens=100, completion_tokens=200, total_tokens=300,
            status="success",
        )

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_log_call_handles_db_error(self, mock_get_conn):
        """Should not raise when database fails."""
        mock_get_conn.side_effect = Exception("DB down")

        OpenAIApiCallRepository.log_call(
            user_id=1, question="Q", model="gpt-4",
            prompt_tokens=10, completion_tokens=20, total_tokens=30,
            status="error", error_message="timeout",
        )

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_get_calls_basic(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [{"id": 1, "question": "Q?"}]

        result = OpenAIApiCallRepository.get_calls()

        assert len(result) == 1

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_get_calls_with_filters(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        OpenAIApiCallRepository.get_calls(
            user_id=1, status="success",
            start_date="2025-01-01", end_date="2025-12-31",
        )

        sql = cur.execute.call_args[0][0]
        assert "user_id" in sql
        assert "status" in sql

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_get_usage_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "total_calls": 50, "unique_users": 5,
            "total_tokens_used": 10000, "total_prompt_tokens": 4000,
            "total_completion_tokens": 6000, "avg_tokens_per_call": 200.0,
            "avg_response_time_ms": 1500.0, "successful_calls": 45,
            "error_calls": 3, "rate_limit_calls": 2,
        }

        result = OpenAIApiCallRepository.get_usage_stats()

        assert result["total_calls"] == 50

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_get_usage_stats_empty(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = OpenAIApiCallRepository.get_usage_stats()

        assert result == {}

    @patch("app.repositories.openai_api_call.get_db_connection")
    def test_get_user_usage(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"user_id": 1, "call_count": 10, "total_tokens": 5000, "avg_tokens_per_call": 500, "last_call": "t"},
        ]

        result = OpenAIApiCallRepository.get_user_usage()

        assert len(result) == 1
        assert result[0]["user_id"] == 1
