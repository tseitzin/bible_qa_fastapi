"""Tests for RecentQuestionsRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.recent_questions import RecentQuestionsRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestRecentQuestionsRepository:

    def test_max_recent_questions_constant(self):
        assert RecentQuestionsRepository.MAX_RECENT_QUESTIONS == 6

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_add_recent_question(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        RecentQuestionsRepository.add_recent_question(user_id=1, question="What is love?")

        assert cur.execute.call_count == 2  # INSERT + DELETE trim
        conn.commit.assert_called_once()

    def test_add_recent_question_skips_empty_user(self):
        """Should return early if user_id is falsy."""
        RecentQuestionsRepository.add_recent_question(user_id=0, question="test")

    def test_add_recent_question_skips_empty_question(self):
        """Should return early if question is falsy."""
        RecentQuestionsRepository.add_recent_question(user_id=1, question="")

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_get_recent_questions(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"id": 1, "question": "Q1?", "asked_at": "2025-01-01"},
        ]

        result = RecentQuestionsRepository.get_recent_questions(user_id=1)

        assert len(result) == 1
        assert result[0]["question"] == "Q1?"

    def test_get_recent_questions_empty_user(self):
        """Should return empty list for falsy user_id."""
        result = RecentQuestionsRepository.get_recent_questions(user_id=0)
        assert result == []

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_get_recent_questions_custom_limit(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        RecentQuestionsRepository.get_recent_questions(user_id=1, limit=3)

        # Verify limit parameter was passed
        call_args = cur.execute.call_args[0][1]
        assert 3 in call_args

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_clear_user_recent_questions(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        RecentQuestionsRepository.clear_user_recent_questions(user_id=1)

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    def test_clear_user_recent_questions_skips_empty_user(self):
        """Should return early for falsy user_id."""
        RecentQuestionsRepository.clear_user_recent_questions(user_id=0)

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_delete_recent_question_success(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 1

        result = RecentQuestionsRepository.delete_recent_question(user_id=1, recent_question_id=5)

        assert result is True
        conn.commit.assert_called_once()

    @patch("app.repositories.recent_questions.get_db_connection")
    def test_delete_recent_question_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 0

        result = RecentQuestionsRepository.delete_recent_question(user_id=1, recent_question_id=999)

        assert result is False

    def test_delete_recent_question_skips_falsy_params(self):
        assert RecentQuestionsRepository.delete_recent_question(user_id=0, recent_question_id=1) is False
        assert RecentQuestionsRepository.delete_recent_question(user_id=1, recent_question_id=0) is False
