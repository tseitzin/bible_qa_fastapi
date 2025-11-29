"""Service for retrieving Bible verses from the database."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

import psycopg2

from app.database import get_db_connection
from app.services.cache_service import CacheService
from app.utils.exceptions import DatabaseError, ValidationError

LOGGER = logging.getLogger(__name__)
REFERENCE_PATTERN = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[A-Za-z][A-Za-z\s]+?)\s+(?P<chapter>\d{1,3})(?::(?P<verse>\d{1,3}))?\s*$",
    re.IGNORECASE,
)

PASSAGE_PATTERN = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[A-Za-z][A-Za-z\s]+?)\s+(?P<rest>\d[\d:\s\-–—]*)\s*$",
    re.IGNORECASE,
)

CANONICAL_BOOK_NAMES = [
    "Genesis",
    "Exodus",
    "Leviticus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1 Samuel",
    "2 Samuel",
    "1 Kings",
    "2 Kings",
    "1 Chronicles",
    "2 Chronicles",
    "Ezra",
    "Nehemiah",
    "Esther",
    "Job",
    "Psalm",
    "Proverbs",
    "Ecclesiastes",
    "Song of Solomon",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
    "Matthew",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1 Corinthians",
    "2 Corinthians",
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1 Thessalonians",
    "2 Thessalonians",
    "1 Timothy",
    "2 Timothy",
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1 Peter",
    "2 Peter",
    "1 John",
    "2 John",
    "3 John",
    "Jude",
    "Revelation",
]

CANONICAL_BOOK_LOOKUP = {name.lower(): name for name in CANONICAL_BOOK_NAMES}
BOOK_SORT_INDEX = {key: idx for idx, key in enumerate(CANONICAL_BOOK_LOOKUP.keys())}

BOOK_ALIASES = {
    "psalms": "Psalm",
    "psalm": "Psalm",
    "song of songs": "Song of Solomon",
    "songs of solomon": "Song of Solomon",
    "canticles": "Song of Solomon",
    "revelations": "Revelation",
    "apocalypse": "Revelation",
}


class BibleService:
    """Service class that encapsulates Bible verse retrieval logic."""

    @staticmethod
    def _normalize_book_name(book: str) -> str:
        if not book or not book.strip():
            raise ValidationError("Book name cannot be empty")

        normalized = re.sub(r"\s+", " ", book.strip())
        normalized_key = normalized.lower()

        if normalized_key in BOOK_ALIASES:
            normalized = BOOK_ALIASES[normalized_key]
            normalized_key = normalized.lower()

        canonical = CANONICAL_BOOK_LOOKUP.get(normalized_key)
        if not canonical:
            raise ValidationError(f"Unknown book name '{normalized}'.")

        return canonical

    @staticmethod
    def _validate_positive_int(value, field_name: str, minimum: int = 1) -> int:
        try:
            coerced = int(value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive programming
            raise ValidationError(f"{field_name} must be an integer.") from exc

        if coerced < minimum:
            raise ValidationError(f"{field_name} must be >= {minimum}.")

        return coerced

    @classmethod
    def _parse_reference(cls, reference: str) -> Tuple[str, int, int]:
        if not reference or not reference.strip():
            raise ValidationError("Reference cannot be empty")

        match = REFERENCE_PATTERN.match(reference)
        if not match:
            raise ValidationError("Invalid reference format. Use 'Book Chapter:Verse'.")

        book = cls._normalize_book_name(match.group("book"))
        chapter = cls._validate_positive_int(match.group("chapter"), "chapter")
        verse_str = match.group("verse")

        if verse_str is None:
            raise ValidationError("Verse component missing. Use 'Book Chapter:Verse'.")

        verse = cls._validate_positive_int(verse_str, "verse")

        return book, chapter, verse

    @classmethod
    def _parse_reference_segment(cls, segment: str, label: str) -> Tuple[int, Optional[int]]:
        if not segment:
            raise ValidationError(f"{label} segment cannot be empty.")

        if ":" in segment:
            chapter_part, verse_part = segment.split(":", 1)
            chapter = cls._validate_positive_int(chapter_part, f"{label}_chapter")
            verse = cls._validate_positive_int(verse_part, f"{label}_verse")
            return chapter, verse

        chapter = cls._validate_positive_int(segment, f"{label}_chapter")
        return chapter, None

    @classmethod
    def _parse_passage_reference(cls, reference: str) -> Tuple[str, int, Optional[int], Optional[int], Optional[int]]:
        if not reference or not reference.strip():
            raise ValidationError("Reference cannot be empty")

        normalized = reference.replace("\u2013", "-").replace("\u2014", "-").strip()
        match = PASSAGE_PATTERN.match(normalized)
        if not match:
            raise ValidationError("Invalid reference format. Use 'Book Chapter[:Verse][-Chapter[:Verse]]'.")

        book = cls._normalize_book_name(match.group("book"))
        rest_raw = (match.group("rest") or "").strip()
        rest = re.sub(r"\s+", "", rest_raw)
        if not rest:
            raise ValidationError("Reference missing chapter information.")

        if "-" in rest:
            start_part, end_part = rest.split("-", 1)
        else:
            start_part, end_part = rest, None

        start_chapter, start_verse = cls._parse_reference_segment(start_part, "start")
        end_chapter: Optional[int] = None
        end_verse: Optional[int] = None

        if end_part:
            if ":" in end_part:
                end_chapter, end_verse = cls._parse_reference_segment(end_part, "end")
            else:
                end_value = cls._validate_positive_int(end_part, "end_value")
                if start_verse is None:
                    end_chapter = end_value
                else:
                    end_chapter = start_chapter
                    end_verse = end_value

        if end_chapter is not None and end_chapter < start_chapter:
            raise ValidationError("end_chapter must be greater than or equal to start_chapter.")

        if end_chapter == start_chapter and start_verse is not None and end_verse is not None and end_verse < start_verse:
            raise ValidationError("end_verse must be greater than or equal to start_verse.")

        return book, start_chapter, start_verse, end_chapter, end_verse

    @staticmethod
    def _format_reference(book: str, start_chapter: int, start_verse: Optional[int], end_chapter: Optional[int], end_verse: Optional[int]) -> str:
        start_part = f"{start_chapter}:{start_verse}" if start_verse is not None else f"{start_chapter}"

        if not end_chapter or end_chapter == start_chapter:
            if start_verse is None and end_verse is None:
                return f"{book} {start_chapter}"

            if start_verse is None and end_verse is not None:
                return f"{book} {start_chapter}:1-{end_verse}"

            end_display = end_verse if end_verse is not None else start_verse
            if end_display == start_verse:
                return f"{book} {start_part}"
            return f"{book} {start_chapter}:{start_verse}-{end_display}"

        end_suffix = f"{end_chapter}:{end_verse}" if end_verse is not None else f"{end_chapter}"
        return f"{book} {start_part}-{end_suffix}"

    def _get_cross_chapter_passage(
        self,
        book: str,
        start_chapter: int,
        start_verse: Optional[int],
        end_chapter: int,
        end_verse: Optional[int],
    ) -> List[dict]:
        canonical_book = self._normalize_book_name(book)
        start_chapter_num = self._validate_positive_int(start_chapter, "start_chapter")
        end_chapter_num = self._validate_positive_int(end_chapter, "end_chapter")

        if end_chapter_num < start_chapter_num:
            raise ValidationError("end_chapter must be greater than or equal to start_chapter.")

        start_verse_num = self._validate_positive_int(start_verse, "start_verse") if start_verse is not None else None
        end_verse_num = self._validate_positive_int(end_verse, "end_verse") if end_verse is not None else None

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT book, chapter, verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                          AND chapter BETWEEN %s AND %s
                        ORDER BY chapter, verse
                        """,
                        (canonical_book, start_chapter_num, end_chapter_num),
                    )
                    rows = cur.fetchall()
        except psycopg2.Error as exc:
            LOGGER.error(
                "Database error retrieving cross-chapter passage %s %s-%s: %s",
                canonical_book,
                start_chapter_num,
                end_chapter_num,
                exc,
            )
            raise DatabaseError("Failed to retrieve passage from database") from exc

        verses: List[dict] = []
        for row in rows:
            chapter = row["chapter"]
            verse = row["verse"]

            if start_verse_num is not None and chapter == start_chapter_num and verse < start_verse_num:
                continue

            if end_verse_num is not None and chapter == end_chapter_num and verse > end_verse_num:
                continue

            verses.append(
                {
                    "reference": f"{row['book']} {chapter}:{verse}",
                    "book": row["book"],
                    "chapter": chapter,
                    "verse": verse,
                    "text": row["text"],
                }
            )

        return verses

    def get_verse(self, reference: str) -> Optional[dict]:
        """Retrieve a single verse by scripture reference string."""
        # Check cache first
        cached = CacheService.get_verse(reference)
        if cached is not None:
            LOGGER.debug(f"Cache hit for verse: {reference}")
            return cached
        
        book, chapter, verse = self._parse_reference(reference)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT book, chapter, verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                          AND chapter = %s
                          AND verse = %s
                        LIMIT 1
                        """,
                        (book, chapter, verse),
                    )
                    result = cur.fetchone()
        except psycopg2.Error as exc:
            LOGGER.error("Database error retrieving verse '%s': %s", reference, exc)
            raise DatabaseError("Failed to retrieve verse from database") from exc

        if not result:
            LOGGER.info("Verse not found for reference '%s'", reference)
            return None

        verse_data = {
            "reference": f"{result['book']} {result['chapter']}:{result['verse']}",
            "book": result["book"],
            "chapter": result["chapter"],
            "verse": result["verse"],
            "text": result["text"],
        }
        
        # Cache the result
        CacheService.set_verse(reference, verse_data)
        
        return verse_data

    def get_passage(self, book: str, chapter: int, start_verse: int, end_verse: int) -> list[dict]:
        """Retrieve a contiguous set of verses within a chapter."""
        # Check cache first
        cached = CacheService.get_passage(book, chapter, start_verse, end_verse)
        if cached is not None:
            LOGGER.debug(f"Cache hit for passage: {book} {chapter}:{start_verse}-{end_verse}")
            return cached
        
        canonical_book = self._normalize_book_name(book)
        chapter_num = self._validate_positive_int(chapter, "chapter")
        start = self._validate_positive_int(start_verse, "start_verse")
        end = self._validate_positive_int(end_verse, "end_verse")

        if end < start:
            raise ValidationError("end_verse must be greater than or equal to start_verse.")

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT book, chapter, verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                          AND chapter = %s
                          AND verse BETWEEN %s AND %s
                        ORDER BY verse
                        """,
                        (canonical_book, chapter_num, start, end),
                    )
                    rows = cur.fetchall()
        except psycopg2.Error as exc:
            LOGGER.error(
                "Database error retrieving passage %s %s:%s-%s: %s",
                canonical_book,
                chapter_num,
                start,
                end,
                exc,
            )
            raise DatabaseError("Failed to retrieve passage from database") from exc

        passage_data = [
            {
                "reference": f"{row['book']} {row['chapter']}:{row['verse']}",
                "book": row["book"],
                "chapter": row["chapter"],
                "verse": row["verse"],
                "text": row["text"],
            }
            for row in rows
        ]
        
        # Cache the result
        CacheService.set_passage(book, chapter, start_verse, end_verse, passage_data)
        
        return passage_data

    def get_passage_by_reference(self, reference: str) -> Optional[dict]:
        """Resolve an arbitrary reference string into a passage payload."""

        book, start_chapter, start_verse, end_chapter, end_verse = self._parse_passage_reference(reference)

        # Multi-chapter passage
        if end_chapter is not None and end_chapter != start_chapter:
            verses = self._get_cross_chapter_passage(book, start_chapter, start_verse, end_chapter, end_verse)
            if not verses:
                return None

            return {
                "reference": self._format_reference(book, start_chapter, start_verse, end_chapter, end_verse),
                "book": book,
                "chapter": start_chapter,
                "end_chapter": end_chapter,
                "start_verse": start_verse,
                "end_verse": end_verse,
                "verses": verses,
            }

        # Single-chapter handling
        if start_verse is None and end_verse is None:
            chapter_payload = self.get_chapter(book, start_chapter)
            if chapter_payload is None:
                return None

            verses = [
                {
                    "reference": f"{book} {start_chapter}:{entry['verse']}",
                    "book": book,
                    "chapter": start_chapter,
                    "verse": entry["verse"],
                    "text": entry["text"],
                }
                for entry in chapter_payload["verses"]
            ]

            if not verses:
                return None

            return {
                "reference": self._format_reference(book, start_chapter, None, None, None),
                "book": book,
                "chapter": start_chapter,
                "end_chapter": None,
                "start_verse": None,
                "end_verse": None,
                "verses": verses,
            }

        resolved_start = start_verse if start_verse is not None else 1
        resolved_end = end_verse if end_verse is not None else resolved_start

        verses = self.get_passage(book, start_chapter, resolved_start, resolved_end)
        if not verses:
            return None

        return {
            "reference": self._format_reference(book, start_chapter, start_verse, start_chapter, end_verse),
            "book": book,
            "chapter": start_chapter,
            "end_chapter": None,
            "start_verse": start_verse if start_verse is not None else resolved_start,
            "end_verse": resolved_end,
            "verses": verses,
        }

    def get_chapter(self, book: str, chapter: int) -> Optional[dict]:
        """Retrieve an entire chapter."""
        # Check cache first
        cached = CacheService.get_chapter(book, chapter)
        if cached is not None:
            LOGGER.debug(f"Cache hit for chapter: {book} {chapter}")
            return cached
        
        canonical_book = self._normalize_book_name(book)
        chapter_num = self._validate_positive_int(chapter, "chapter")

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                          AND chapter = %s
                        ORDER BY verse
                        """,
                        (canonical_book, chapter_num),
                    )
                    verses = cur.fetchall()
        except psycopg2.Error as exc:
            LOGGER.error("Database error retrieving chapter %s %s: %s", canonical_book, chapter_num, exc)
            raise DatabaseError("Failed to retrieve chapter from database") from exc

        if not verses:
            return None

        chapter_data = {
            "book": canonical_book,
            "chapter": chapter_num,
            "verses": [
                {"verse": row["verse"], "text": row["text"]}
                for row in verses
            ],
        }
        
        # Cache the result
        CacheService.set_chapter(book, chapter, chapter_data)
        
        return chapter_data

    def search_verses(self, keyword: str, limit: int = 20) -> list[dict]:
        """Perform a lightweight text search across verses."""
        if not keyword or not keyword.strip():
            raise ValidationError("Search keyword cannot be empty")

        # Check cache first
        cached = CacheService.get_search(keyword, limit)
        if cached is not None:
            LOGGER.debug(f"Cache hit for search: {keyword} (limit={limit})")
            return cached
        
        limit_value = self._validate_positive_int(limit, "limit")
        limit_value = min(limit_value, 500)
        term = f"%{keyword.strip()}%"

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT book, chapter, verse, text
                        FROM bible_verses
                        WHERE text ILIKE %s
                        ORDER BY book, chapter, verse
                        LIMIT %s
                        """,
                        (term, limit_value),
                    )
                    matches = cur.fetchall()
        except psycopg2.Error as exc:
            LOGGER.error("Database error searching verses for '%s': %s", keyword, exc)
            raise DatabaseError("Failed to search verses") from exc

        results = [
            {
                "reference": f"{row['book']} {row['chapter']}:{row['verse']}",
                "book": row["book"],
                "chapter": row["chapter"],
                "verse": row["verse"],
                "text": row["text"],
            }
            for row in matches
        ]
        
        # Cache the results
        CacheService.set_search(keyword, limit, results)
        
        return results

    def list_books(self) -> list[dict]:
        """Return overview information for every Bible book present in the dataset."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT book,
                               COUNT(DISTINCT chapter) AS total_chapters,
                               COUNT(*) AS total_verses
                        FROM bible_verses
                        GROUP BY book
                        """
                    )
                    rows = cur.fetchall()
        except psycopg2.Error as exc:
            LOGGER.error("Database error listing Bible books: %s", exc)
            raise DatabaseError("Failed to list Bible books") from exc

        def sort_key(row):
            return BOOK_SORT_INDEX.get(row["book"].lower(), len(BOOK_SORT_INDEX))

        ordered = sorted(rows, key=sort_key)

        return [
            {
                "book": row["book"],
                "total_chapters": row["total_chapters"],
                "total_verses": row["total_verses"],
            }
            for row in ordered
        ]

    def get_book_info(self, book: str) -> Optional[dict]:
        """Provide aggregate metadata for a specific book."""
        canonical_book = self._normalize_book_name(book)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT chapter) AS total_chapters,
                               COUNT(*) AS total_verses
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                        """,
                        (canonical_book,),
                    )
                    summary = cur.fetchone()

                    if not summary or summary["total_chapters"] == 0:
                        return None

                    cur.execute(
                        """
                        SELECT chapter, verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                        ORDER BY chapter ASC, verse ASC
                        LIMIT 1
                        """,
                        (canonical_book,),
                    )
                    first = cur.fetchone()

                    cur.execute(
                        """
                        SELECT chapter, verse, text
                        FROM bible_verses
                        WHERE LOWER(book) = LOWER(%s)
                        ORDER BY chapter DESC, verse DESC
                        LIMIT 1
                        """,
                        (canonical_book,),
                    )
                    last = cur.fetchone()
        except psycopg2.Error as exc:
            LOGGER.error("Database error retrieving book info for %s: %s", canonical_book, exc)
            raise DatabaseError("Failed to retrieve book metadata") from exc

        def serialize_reference(row):
            if not row:
                return None
            return {
                "reference": f"{canonical_book} {row['chapter']}:{row['verse']}",
                "chapter": row["chapter"],
                "verse": row["verse"],
                "text": row["text"],
            }

        return {
            "book": canonical_book,
            "total_chapters": summary["total_chapters"],
            "total_verses": summary["total_verses"],
            "first_reference": serialize_reference(first),
            "last_reference": serialize_reference(last),
        }


bible_service = BibleService()


def get_bible_service() -> BibleService:
    """Dependency injector for retrieving the singleton BibleService instance."""
    return bible_service
