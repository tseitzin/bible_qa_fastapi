"""Repository for topical Bible study entries."""
import json
from typing import Any, List, Optional

from app.database import get_db_connection


class TopicIndexRepository:
    """Repository for topical Bible study entries."""

    @staticmethod
    def search_topics(keyword: Optional[str] = None, limit: int = 10) -> List[dict[str, Any]]:
        pattern = f"%{keyword}%" if keyword else "%"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic, summary, keywords, reference_entries
                    FROM topic_index
                    WHERE topic ILIKE %s
                       OR summary ILIKE %s
                       OR EXISTS (
                            SELECT 1 FROM unnest(keywords) kw WHERE kw ILIKE %s
                       )
                    ORDER BY topic ASC
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, limit),
                )
                rows = cur.fetchall()
                for row in rows:
                    keywords = row.get("keywords")
                    if keywords is None:
                        row["keywords"] = []
                    else:
                        row["keywords"] = list(keywords)
                    references = row.pop("reference_entries", [])
                    if isinstance(references, str):
                        references = json.loads(references)
                    row["references"] = references
                return rows
