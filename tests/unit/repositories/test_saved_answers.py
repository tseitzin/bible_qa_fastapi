"""Tests for SavedAnswersRepository."""
from unittest.mock import patch, MagicMock

from app.repositories.saved_answers import SavedAnswersRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestSavedAnswersRepository:

    @patch("app.repositories.saved_answers.get_db_connection")
    def test_admin_delete_saved_answer_success(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 1

        result = SavedAnswersRepository.admin_delete_saved_answer(10)

        assert result is True
        conn.commit.assert_called_once()

    @patch("app.repositories.saved_answers.get_db_connection")
    def test_admin_delete_saved_answer_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 0

        result = SavedAnswersRepository.admin_delete_saved_answer(999)

        assert result is False

    @patch("app.repositories.saved_answers.QuestionRepository.get_root_question_id", return_value=1)
    @patch("app.repositories.saved_answers.get_db_connection")
    def test_save_answer(self, mock_get_conn, mock_root):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "id": 5, "user_id": 1, "question_id": 1,
            "tags": ["grace"], "saved_at": "2025-01-01",
        }

        result = SavedAnswersRepository.save_answer(user_id=1, question_id=3, tags=["grace"])

        assert result["id"] == 5
        mock_root.assert_called_once_with(3)
        conn.commit.assert_called_once()

    @patch("app.repositories.saved_answers.QuestionRepository.get_conversation_thread")
    @patch("app.repositories.saved_answers.get_db_connection")
    def test_get_user_saved_answers(self, mock_get_conn, mock_thread):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "id": 1, "question_id": 10, "question": "Q?", "answer": "A",
                "tags": ["faith"], "saved_at": "t", "parent_question_id": None,
            }
        ]
        mock_thread.return_value = []

        result = SavedAnswersRepository.get_user_saved_answers(user_id=1)

        assert len(result) == 1
        assert result[0]["question"] == "Q?"
        assert result[0]["conversation_thread"] == []

    @patch("app.repositories.saved_answers.get_db_connection")
    def test_delete_saved_answer(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.rowcount = 1

        result = SavedAnswersRepository.delete_saved_answer(user_id=1, saved_answer_id=5)

        assert result is True
        conn.commit.assert_called_once()

    @patch("app.repositories.saved_answers.get_db_connection")
    def test_get_user_tags(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [{"tag": "faith"}, {"tag": "hope"}]

        result = SavedAnswersRepository.get_user_tags(user_id=1)

        assert result == ["faith", "hope"]

    @patch("app.repositories.saved_answers.QuestionRepository.get_conversation_thread")
    @patch("app.repositories.saved_answers.get_db_connection")
    def test_search_saved_answers_by_tag(self, mock_get_conn, mock_thread):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "id": 1, "question_id": 10, "question": "Q?", "answer": "A",
                "tags": ["faith"], "saved_at": "t", "parent_question_id": None,
            }
        ]
        mock_thread.return_value = []

        result = SavedAnswersRepository.search_saved_answers(user_id=1, tag="faith")

        assert len(result) == 1

    @patch("app.repositories.saved_answers.QuestionRepository.get_conversation_thread")
    @patch("app.repositories.saved_answers.get_db_connection")
    def test_search_saved_answers_by_query(self, mock_get_conn, mock_thread):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []
        mock_thread.return_value = []

        result = SavedAnswersRepository.search_saved_answers(user_id=1, query="love")

        assert result == []

    @patch("app.repositories.saved_answers.SavedAnswersRepository.get_user_saved_answers")
    def test_search_saved_answers_no_filters(self, mock_get_all):
        """When no tag or query, should delegate to get_user_saved_answers."""
        mock_get_all.return_value = [{"id": 1}]

        result = SavedAnswersRepository.search_saved_answers(user_id=1)

        assert result == [{"id": 1}]
        mock_get_all.assert_called_once_with(1)
