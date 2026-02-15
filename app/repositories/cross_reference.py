"""Read-only access to Treasury of Scripture Knowledge cross references."""
import json
from typing import Any, List

from app.database import get_db_connection


class CrossReferenceRepository:
    """Read-only access to Treasury of Scripture Knowledge cross references."""

    @staticmethod
    def get_cross_references(book: str, chapter: int, verse: int) -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reference_data
                    FROM cross_references
                    WHERE LOWER(book) = LOWER(%s)
                      AND chapter = %s
                      AND verse = %s
                    LIMIT 1
                    """,
                    (book, chapter, verse),
                )
                row = cur.fetchone()
                data = row["reference_data"] if row else []
                if isinstance(data, str):
                    return json.loads(data)
                return data
