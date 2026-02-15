"""Tests for CrossReferenceRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.cross_reference import CrossReferenceRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestCrossReferenceRepository:

    @patch("app.repositories.cross_reference.get_db_connection")
    def test_get_cross_references_with_data(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        refs = [{"reference": "Romans 5:1", "note": "cf."}]
        cur.fetchone.return_value = {"reference_data": refs}

        result = CrossReferenceRepository.get_cross_references("John", 3, 16)

        assert len(result) == 1
        assert result[0]["reference"] == "Romans 5:1"

    @patch("app.repositories.cross_reference.get_db_connection")
    def test_get_cross_references_json_string(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        refs = [{"reference": "Romans 5:1"}]
        cur.fetchone.return_value = {"reference_data": json.dumps(refs)}

        result = CrossReferenceRepository.get_cross_references("John", 3, 16)

        assert len(result) == 1

    @patch("app.repositories.cross_reference.get_db_connection")
    def test_get_cross_references_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = CrossReferenceRepository.get_cross_references("Nonexistent", 1, 1)

        assert result == []
