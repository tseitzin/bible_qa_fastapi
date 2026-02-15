"""Tests for LexiconRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.lexicon import LexiconRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestLexiconRepository:

    def test_get_entry_returns_none_when_no_params(self):
        """Should return None when neither strongs_number nor lemma provided."""
        result = LexiconRepository.get_entry()
        assert result is None

    @patch("app.repositories.lexicon.get_db_connection")
    def test_get_entry_by_strongs_number(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "strongs_number": "G26",
            "lemma": "agape",
            "transliteration": "agapē",
            "pronunciation": "ag-ah'-pay",
            "language": "Greek",
            "definition": "Love, affection",
            "usage": "love",
            "reference_list": ["1 Cor 13:4"],
            "metadata": None,
        }

        result = LexiconRepository.get_entry(strongs_number="G26")

        assert result["strongs_number"] == "G26"
        assert result["references"] == ["1 Cor 13:4"]

    @patch("app.repositories.lexicon.get_db_connection")
    def test_get_entry_by_lemma(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "strongs_number": "G26",
            "lemma": "agape",
            "transliteration": "agapē",
            "pronunciation": "ag-ah'-pay",
            "language": "Greek",
            "definition": "Love",
            "usage": "love",
            "reference_list": json.dumps(["1 Cor 13:4"]),
            "metadata": json.dumps({"source": "strongs"}),
        }

        result = LexiconRepository.get_entry(lemma="agape")

        assert result["references"] == ["1 Cor 13:4"]
        assert result["metadata"] == {"source": "strongs"}

    @patch("app.repositories.lexicon.get_db_connection")
    def test_get_entry_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = LexiconRepository.get_entry(strongs_number="G99999")

        assert result is None
