"""Unit tests for BibleService."""
import pytest
from unittest.mock import Mock, patch
import psycopg2

from app.services.bible_service import BibleService, get_bible_service
from app.utils.exceptions import ValidationError, DatabaseError


class TestBibleService:
    """Test cases for BibleService reference parsing and retrieval."""

    def setup_method(self):
        self.service = BibleService()

    def test_parse_reference_valid(self):
        """Parsing a standard reference returns canonical components."""
        book, chapter, verse = self.service._parse_reference("John 3:16")
        assert book == "John"
        assert chapter == 3
        assert verse == 16

    def test_parse_reference_with_alias(self):
        """Alias book names are normalized to canonical names."""
        book, chapter, verse = self.service._parse_reference("Psalms 23:1")
        assert book == "Psalm"
        assert chapter == 23
        assert verse == 1

    @pytest.mark.parametrize("reference", ["", "   ", "John three sixteen", "Unknown 1:1", "John 3"])
    def test_parse_reference_invalid(self, reference):
        """Invalid references raise ValidationError."""
        with pytest.raises(ValidationError):
            self.service._parse_reference(reference)

    @patch("app.services.bible_service.get_db_connection")
    def test_get_verse_success(self, mock_get_db_connection):
        """Retrieving a verse returns the formatted dictionary."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {
            "book": "John",
            "chapter": 3,
            "verse": 16,
            "text": "For God so loved the world...",
        }
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = self.service.get_verse("John 3:16")
        assert result["reference"] == "John 3:16"
        assert "text" in result

    @patch("app.services.bible_service.get_db_connection")
    def test_get_verse_not_found(self, mock_get_db_connection):
        """Missing verses return None."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        assert self.service.get_verse("John 3:99") is None

    @patch("app.services.bible_service.get_db_connection")
    def test_get_verse_database_error(self, mock_get_db_connection):
        """Database errors are wrapped in DatabaseError."""
        mock_conn = Mock()
        mock_conn.cursor.side_effect = psycopg2.Error("connection lost")

        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        with pytest.raises(DatabaseError):
            self.service.get_verse("John 3:16")

    def test_get_bible_service_singleton(self):
        """Dependency helper returns the shared BibleService instance."""
        instance = get_bible_service()
        other_instance = get_bible_service()
        assert isinstance(instance, BibleService)
        assert instance is other_instance
