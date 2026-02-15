"""Repository for devotional scaffolding templates."""
import json
from typing import Any, List, Optional

from app.database import get_db_connection


class DevotionalTemplateRepository:
    """Repository for devotional scaffolding templates."""

    @staticmethod
    def list_templates() -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slug, title, body, prompt_1, prompt_2, default_passage, metadata
                    FROM devotional_templates
                    ORDER BY title ASC
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows

    @staticmethod
    def get_template(slug: str) -> Optional[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slug, title, body, prompt_1, prompt_2, default_passage, metadata
                    FROM devotional_templates
                    WHERE LOWER(slug) = LOWER(%s)
                    LIMIT 1
                    """,
                    (slug,),
                )
                template = cur.fetchone()
                if not template:
                    return None
                metadata = template.get("metadata")
                if isinstance(metadata, str):
                    template["metadata"] = json.loads(metadata)
                return template
