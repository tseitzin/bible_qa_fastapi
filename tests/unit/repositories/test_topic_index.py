"""Tests for TopicIndexRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.topic_index import TopicIndexRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestTopicIndexRepository:

    @patch("app.repositories.topic_index.get_db_connection")
    def test_search_topics_with_keyword(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "topic": "Faith",
                "summary": "Trust in God",
                "keywords": ["belief", "trust"],
                "reference_entries": [{"passage": "Heb 11:1"}],
            }
        ]

        result = TopicIndexRepository.search_topics(keyword="faith")

        assert len(result) == 1
        assert result[0]["topic"] == "Faith"
        assert result[0]["keywords"] == ["belief", "trust"]
        assert result[0]["references"] == [{"passage": "Heb 11:1"}]

    @patch("app.repositories.topic_index.get_db_connection")
    def test_search_topics_json_string_references(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {
                "topic": "Love",
                "summary": "God's love",
                "keywords": None,
                "reference_entries": json.dumps([{"passage": "1 John 4:8"}]),
            }
        ]

        result = TopicIndexRepository.search_topics()

        assert result[0]["keywords"] == []
        assert result[0]["references"] == [{"passage": "1 John 4:8"}]

    @patch("app.repositories.topic_index.get_db_connection")
    def test_search_topics_empty(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        result = TopicIndexRepository.search_topics(keyword="nonexistent")

        assert result == []
