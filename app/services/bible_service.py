"""Service for retrieving Bible verses from the database."""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

import psycopg2

from app.database import get_db_connection
from app.utils.exceptions import DatabaseError, ValidationError

LOGGER = logging.getLogger(__name__)
REFERENCE_PATTERN = re.compile(
    r"^\s*(?P<book>(?:[1-3]\s*)?[A-Za-z][A-Za-z\s]+?)\s+(?P<chapter>\d{1,3})(?::(?P<verse>\d{1,3}))?\s*$",
    re.IGNORECASE,
)

CANONICAL_BOOKS = {
    "genesis",
    "exodus",
    "leviticus",
    "numbers",
    "deuteronomy",
    "joshua",
    "judges",
    "ruth",
    "1 samuel",
    "2 samuel",
    "1 kings",
    "2 kings",
    "1 chronicles",
    "2 chronicles",
    "ezra",
    "nehemiah",
    "esther",
    "job",
    "psalm",
    "proverbs",
    "ecclesiastes",
    "song of solomon",
    "isaiah",
    "jeremiah",
    "lamentations",
    "ezekiel",
    "daniel",
    "hosea",
    "joel",
    "amos",
    "obadiah",
    "jonah",
    "micah",
    "nahum",
    "habakkuk",
    "zephaniah",
    "haggai",
    "zechariah",
    "malachi",
    "matthew",
    "mark",
    "luke",
    "john",
    "acts",
    "romans",
    "1 corinthians",
    "2 corinthians",
    "galatians",
    "ephesians",
    "philippians",
    "colossians",
    "1 thessalonians",
    "2 thessalonians",
    "1 timothy",
    "2 timothy",
    "titus",
    "philemon",
    "hebrews",
    "james",
    "1 peter",
    "2 peter",
    "1 john",
    "2 john",
    "3 john",
    "jude",
    "revelation",
}

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
    def _parse_reference(reference: str) -> Tuple[str, int, int]:
        if not reference or not reference.strip():
            raise ValidationError("Reference cannot be empty")

        match = REFERENCE_PATTERN.match(reference)
        if not match:
            raise ValidationError("Invalid reference format. Use 'Book Chapter:Verse'.")

        book = re.sub(r"\s+", " ", match.group("book").strip())
        book_key = book.lower()
        if book_key in BOOK_ALIASES:
            book = BOOK_ALIASES[book_key]
            book_key = book.lower()

        if book_key not in CANONICAL_BOOKS:
            raise ValidationError(f"Unknown book name '{book}'.")

        chapter_str = match.group("chapter")
        verse_str = match.group("verse")

        if verse_str is None:
            raise ValidationError("Verse component missing. Use 'Book Chapter:Verse'.")

        try:
            chapter = int(chapter_str)
            verse = int(verse_str)
        except ValueError as exc:  # pragma: no cover - defensive programming
            raise ValidationError("Chapter and verse must be integers.") from exc

        return book, chapter, verse

    def get_verse(self, reference: str) -> Optional[dict]:
        """Retrieve a single verse by scripture reference string."""
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

        return {
            "reference": f"{result['book']} {result['chapter']}:{result['verse']}",
            "book": result["book"],
            "chapter": result["chapter"],
            "verse": result["verse"],
            "text": result["text"],
        }


bible_service = BibleService()


def get_bible_service() -> BibleService:
    """Dependency injector for retrieving the singleton BibleService instance."""
    return bible_service
