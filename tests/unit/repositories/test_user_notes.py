"""Tests for UserNotesRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.user_notes import UserNotesRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestUserNotesRepository:

    @patch("app.repositories.user_notes.get_db_connection")
    def test_create_note_basic(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "id": 1, "user_id": 1, "question_id": None,
            "content": "My note", "metadata": None,
            "source": None, "created_at": "t", "updated_at": "t",
        }

        result = UserNotesRepository.create_note(user_id=1, content="My note")

        assert result["id"] == 1
        assert result["content"] == "My note"
        conn.commit.assert_called_once()

    @patch("app.repositories.user_notes.get_db_connection")
    def test_create_note_with_metadata(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        metadata = {"verse": "John 3:16"}
        cur.fetchone.return_value = {
            "id": 2, "user_id": 1, "question_id": 5,
            "content": "Note", "metadata": json.dumps(metadata),
            "source": "bible", "created_at": "t", "updated_at": "t",
        }

        result = UserNotesRepository.create_note(
            user_id=1, content="Note", question_id=5,
            metadata=metadata, source="bible",
        )

        assert result["metadata"] == metadata

    @patch("app.repositories.user_notes.get_db_connection")
    def test_list_notes_basic(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "id": 1, "user_id": 1, "question_id": None,
                "content": "Note 1", "metadata": None,
                "source": None, "created_at": "t", "updated_at": "t",
            },
        ]

        result = UserNotesRepository.list_notes(user_id=1)

        assert len(result) == 1

    @patch("app.repositories.user_notes.get_db_connection")
    def test_list_notes_with_question_filter(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        UserNotesRepository.list_notes(user_id=1, question_id=5)

        # Verify the SQL includes question_id filter
        sql = cur.execute.call_args[0][0]
        assert "question_id" in sql

    @patch("app.repositories.user_notes.get_db_connection")
    def test_list_notes_deserializes_metadata_string(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "id": 1, "user_id": 1, "question_id": None,
                "content": "Note", "metadata": '{"key": "value"}',
                "source": None, "created_at": "t", "updated_at": "t",
            },
        ]

        result = UserNotesRepository.list_notes(user_id=1)

        assert result[0]["metadata"] == {"key": "value"}
