"""Tests for DevotionalTemplateRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.devotional_template import DevotionalTemplateRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestDevotionalTemplateRepository:

    @patch("app.repositories.devotional_template.get_db_connection")
    def test_list_templates(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "slug": "classic", "title": "Classic", "body": "body",
                "prompt_1": "p1", "prompt_2": "p2",
                "default_passage": "John 3:16", "metadata": {},
            },
        ]

        result = DevotionalTemplateRepository.list_templates()

        assert len(result) == 1
        assert result[0]["slug"] == "classic"

    @patch("app.repositories.devotional_template.get_db_connection")
    def test_list_templates_deserializes_metadata(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "slug": "s", "title": "T", "body": "b",
                "prompt_1": "p1", "prompt_2": "p2",
                "default_passage": None, "metadata": '{"k": "v"}',
            },
        ]

        result = DevotionalTemplateRepository.list_templates()

        assert result[0]["metadata"] == {"k": "v"}

    @patch("app.repositories.devotional_template.get_db_connection")
    def test_get_template(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "slug": "classic", "title": "Classic", "body": "body",
            "prompt_1": "p1", "prompt_2": "p2",
            "default_passage": None, "metadata": {},
        }

        result = DevotionalTemplateRepository.get_template("classic")

        assert result["title"] == "Classic"

    @patch("app.repositories.devotional_template.get_db_connection")
    def test_get_template_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = DevotionalTemplateRepository.get_template("nonexistent")

        assert result is None
