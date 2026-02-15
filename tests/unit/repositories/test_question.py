"""Tests for QuestionRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.question import QuestionRepository


class TestQuestionRepository:
    """Tests for QuestionRepository."""

    @patch("app.repositories.question.get_db_connection")
    def test_delete_question_success(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 1

        result = QuestionRepository.delete_question(42)

        assert result is True
        assert cur.execute.call_count == 2  # delete answers, then delete question
        conn.commit.assert_called_once()

    @patch("app.repositories.question.get_db_connection")
    def test_delete_question_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 0

        result = QuestionRepository.delete_question(999)

        assert result is False

    @patch("app.repositories.question.get_db_connection")
    def test_create_question(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 123}

        result = QuestionRepository.create_question(user_id=1, question="What is faith?")

        assert result == 123
        conn.commit.assert_called_once()

    @patch("app.repositories.question.get_db_connection")
    def test_create_question_with_parent(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 456}

        result = QuestionRepository.create_question(
            user_id=1, question="Follow up?", parent_question_id=123
        )

        assert result == 456
        # Verify parent_question_id was passed
        call_args = cur.execute.call_args
        assert 123 in call_args[0][1]

    @patch("app.repositories.question.get_db_connection")
    def test_create_answer(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        QuestionRepository.create_answer(question_id=1, answer="God is love.")

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("app.repositories.question.get_db_connection")
    def test_get_question_history(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"id": 1, "question": "Q1", "created_at": "2025-01-01", "answer": "A1"},
        ]

        result = QuestionRepository.get_question_history(user_id=1, limit=10)

        assert len(result) == 1
        assert result[0]["question"] == "Q1"

    @patch("app.repositories.question.get_db_connection")
    def test_get_root_question_id(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 100}

        result = QuestionRepository.get_root_question_id(105)

        assert result == 100

    @patch("app.repositories.question.get_db_connection")
    def test_get_root_question_id_returns_self_when_no_parent(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = QuestionRepository.get_root_question_id(42)

        assert result == 42

    @patch("app.repositories.question.get_db_connection")
    def test_get_conversation_thread(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"id": 1, "question": "Root?", "parent_question_id": None, "asked_at": "t", "answer": "A", "depth": 0},
            {"id": 2, "question": "Follow?", "parent_question_id": 1, "asked_at": "t", "answer": "B", "depth": 1},
        ]

        result = QuestionRepository.get_conversation_thread(1)

        assert len(result) == 2
        assert result[0]["depth"] == 0
        assert result[1]["depth"] == 1


def _setup_db(mock_get_conn):
    """Helper to set up mock DB connection and cursor."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor
