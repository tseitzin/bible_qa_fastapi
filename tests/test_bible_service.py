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

    def test_parse_passage_reference_range(self):
        book, chapter, start, end_chapter, end = self.service._parse_passage_reference("John 3:16-17")
        assert book == "John"
        assert chapter == 3
        assert start == 16
        assert end_chapter == 3
        assert end == 17

    def test_parse_passage_reference_entire_chapter(self):
        book, chapter, start, end_chapter, end = self.service._parse_passage_reference("Psalm 23")
        assert book == "Psalm"
        assert chapter == 23
        assert start is None
        assert end_chapter is None
        assert end is None

    def test_parse_passage_reference_cross_chapter_with_verses(self):
        book, chapter, start, end_chapter, end = self.service._parse_passage_reference("Genesis 39:1-40:5")
        assert book == "Genesis"
        assert chapter == 39
        assert start == 1
        assert end_chapter == 40
        assert end == 5

    def test_parse_passage_reference_chapter_range(self):
        book, chapter, start, end_chapter, end = self.service._parse_passage_reference("Genesis 39-50")
        assert book == "Genesis"
        assert chapter == 39
        assert start is None
        assert end_chapter == 50
        assert end is None

    def test_parse_passage_reference_end_chapter_less_than_start(self):
        with pytest.raises(ValidationError):
            self.service._parse_passage_reference("Genesis 5-3")

    def test_parse_passage_reference_end_verse_less_than_start(self):
        with pytest.raises(ValidationError):
            self.service._parse_passage_reference("Genesis 3:10-3:2")

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

    @patch("app.services.bible_service.get_db_connection")
    def test_get_passage_success(self, mock_get_db_connection):
        """Passage retrieval returns an ordered list of verses."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"book": "John", "chapter": 3, "verse": 16, "text": "sample"},
            {"book": "John", "chapter": 3, "verse": 17, "text": "sample"},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = self.service.get_passage("John", 3, 16, 17)
        assert len(result) == 2
        assert result[0]["reference"] == "John 3:16"

    def test_get_passage_invalid_range(self):
        """start_verse > end_verse raises ValidationError."""
        with pytest.raises(ValidationError):
            self.service.get_passage("John", 3, 20, 10)

    def test_get_passage_by_reference_range(self, monkeypatch):
        sample = [
            {"reference": "John 3:16", "book": "John", "chapter": 3, "verse": 16, "text": "sample"},
            {"reference": "John 3:17", "book": "John", "chapter": 3, "verse": 17, "text": "sample"},
        ]

        monkeypatch.setattr(
            BibleService,
            "get_passage",
            lambda self, book, chapter, start, end: sample,
        )

        result = self.service.get_passage_by_reference("John 3:16-17")

        assert result["start_verse"] == 16
        assert result["end_verse"] == 17
        assert len(result["verses"]) == 2

    def test_get_passage_by_reference_chapter(self, monkeypatch):
        monkeypatch.setattr(
            BibleService,
            "get_chapter",
            lambda self, book, chapter: {
                "book": book,
                "chapter": chapter,
                "verses": [
                    {"verse": 1, "text": "The Lord is my shepherd"},
                    {"verse": 2, "text": "He makes me lie down"},
                ],
            },
        )

        result = self.service.get_passage_by_reference("Psalm 23")

        assert result["start_verse"] is None
        assert len(result["verses"]) == 2
        assert result["verses"][0]["reference"] == "Psalm 23:1"

    def test_get_passage_by_reference_missing_chapter(self, monkeypatch):
        monkeypatch.setattr(BibleService, "get_chapter", lambda self, book, chapter: None)

        assert self.service.get_passage_by_reference("Nahum 1") is None

    def test_get_passage_by_reference_empty_chapter_list(self, monkeypatch):
        monkeypatch.setattr(
            BibleService,
            "get_chapter",
            lambda self, book, chapter: {"book": book, "chapter": chapter, "verses": []},
        )

        assert self.service.get_passage_by_reference("Nahum 1") is None

    def test_get_passage_by_reference_empty_passage(self, monkeypatch):
        monkeypatch.setattr(
            BibleService,
            "get_passage",
            lambda self, book, chapter, start, end: [],
        )

        assert self.service.get_passage_by_reference("John 3:16-17") is None

    def test_get_passage_by_reference_invalid_format(self):
        with pytest.raises(ValidationError):
            self.service.get_passage_by_reference("invalid reference text")

    def test_get_passage_by_reference_cross_chapter(self, monkeypatch):
        sample = [
            {"reference": "Genesis 39:1", "book": "Genesis", "chapter": 39, "verse": 1, "text": "v1"},
            {"reference": "Genesis 40:1", "book": "Genesis", "chapter": 40, "verse": 1, "text": "v2"},
        ]

        monkeypatch.setattr(
            BibleService,
            "_get_cross_chapter_passage",
            lambda self, book, start_chapter, start_verse, end_chapter, end_verse: sample,
        )

        result = self.service.get_passage_by_reference("Genesis 39-40")

        assert result["end_chapter"] == 40
        assert result["start_verse"] is None
        assert result["end_verse"] is None
        assert result["verses"] == sample

    def test_get_passage_by_reference_partial_chapter_range(self, monkeypatch):
        sample = [
            {"reference": "Psalm 23:1", "book": "Psalm", "chapter": 23, "verse": 1, "text": "v1"},
            {"reference": "Psalm 23:5", "book": "Psalm", "chapter": 23, "verse": 5, "text": "v5"},
        ]

        captured = {}

        def fake_get_passage(self, book, chapter, start, end):
            captured["args"] = (book, chapter, start, end)
            return sample

        monkeypatch.setattr(BibleService, "get_passage", fake_get_passage)

        result = self.service.get_passage_by_reference("Psalm 23-23:5")

        assert captured["args"] == ("Psalm", 23, 1, 5)
        assert result["start_verse"] == 1
        assert result["end_verse"] == 5
        assert len(result["verses"]) == 2

    def test_get_passage_by_reference_single_verse(self, monkeypatch):
        sample = [
            {"reference": "John 3:16", "book": "John", "chapter": 3, "verse": 16, "text": "v1"},
        ]

        monkeypatch.setattr(
            BibleService,
            "get_passage",
            lambda self, book, chapter, start, end: sample,
        )

        result = self.service.get_passage_by_reference("John 3:16")

        assert result["reference"] == "John 3:16"
        assert result["start_verse"] == 16
        assert result["end_verse"] == 16
        assert len(result["verses"]) == 1

    @patch("app.services.bible_service.get_db_connection")
    def test_get_cross_chapter_passage_filters_edges(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"book": "Genesis", "chapter": 39, "verse": 1, "text": "a"},
            {"book": "Genesis", "chapter": 39, "verse": 5, "text": "b"},
            {"book": "Genesis", "chapter": 40, "verse": 1, "text": "c"},
            {"book": "Genesis", "chapter": 40, "verse": 3, "text": "d"},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = self.service._get_cross_chapter_passage("Genesis", 39, 2, 40, 2)

        assert len(result) == 2
        assert result[0]["reference"] == "Genesis 39:5"
        assert result[1]["reference"] == "Genesis 40:1"

    def test_get_cross_chapter_passage_invalid_range(self):
        with pytest.raises(ValidationError):
            self.service._get_cross_chapter_passage("Genesis", 40, None, 39, None)

        @patch("app.services.bible_service.get_db_connection")
        def test_get_cross_chapter_passage_database_error(self, mock_get_db_connection):
            mock_conn = Mock()
            mock_conn.cursor.side_effect = psycopg2.Error("db boom")
            mock_get_db_connection.return_value.__enter__.return_value = mock_conn
            mock_get_db_connection.return_value.__exit__.return_value = None

            with pytest.raises(DatabaseError):
                self.service._get_cross_chapter_passage("Genesis", 39, None, 40, None)

    def test_get_passage_by_reference_cross_chapter_empty(self, monkeypatch):
        monkeypatch.setattr(
            BibleService,
            "_get_cross_chapter_passage",
            lambda self, book, start_chapter, start_verse, end_chapter, end_verse: [],
        )

        assert self.service.get_passage_by_reference("Genesis 39-40") is None

    @patch("app.services.bible_service.get_db_connection")
    def test_get_chapter_returns_none_when_empty(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        assert self.service.get_chapter("John", 99) is None

    @patch("app.services.bible_service.get_db_connection")
    def test_get_chapter_database_error(self, mock_get_db_connection):
        mock_conn = Mock()
        mock_conn.cursor.side_effect = psycopg2.Error("boom")
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        with pytest.raises(DatabaseError):
            self.service.get_chapter("John", 3)

    @patch("app.services.bible_service.get_db_connection")
    def test_get_chapter_success(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"verse": 1, "text": "a"},
            {"verse": 2, "text": "b"},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = self.service.get_chapter("John", 3)

        assert result["book"] == "John"
        assert result["chapter"] == 3
        assert len(result["verses"]) == 2

    def test_search_verses_empty_keyword_raises(self):
        with pytest.raises(ValidationError):
            self.service.search_verses(" ")

    @patch("app.services.bible_service.get_db_connection")
    def test_search_verses_limit_clamped(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        self.service.search_verses("love", limit=1000)
        params = mock_cursor.execute.call_args[0][1]
        assert params[1] == 100  # limit clamped to 100

    @patch("app.services.bible_service.get_db_connection")
    def test_list_books_orders_results(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {"book": "Revelation", "total_chapters": 22, "total_verses": 404},
            {"book": "Genesis", "total_chapters": 50, "total_verses": 1533},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        result = self.service.list_books()
        assert [book["book"] for book in result] == ["Genesis", "Revelation"]

    @patch("app.services.bible_service.get_db_connection")
    def test_get_book_info_success(self, mock_get_db_connection):
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            {"total_chapters": 21, "total_verses": 879},
            {"chapter": 1, "verse": 1, "text": "In the beginning"},
            {"chapter": 22, "verse": 21, "text": "Amen"},
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_get_db_connection.return_value.__exit__.return_value = None

        info = self.service.get_book_info("Revelation")
        assert info["total_chapters"] == 21
        assert info["first_reference"]["reference"].startswith("Revelation 1:1")

