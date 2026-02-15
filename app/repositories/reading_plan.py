"""Repository backing curated reading plans."""
import json
from typing import Any, List, Optional

from app.database import get_db_connection


class ReadingPlanRepository:
    """Repository backing curated reading plans."""

    @staticmethod
    def list_plans() -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, slug, name, description, duration_days, metadata
                    FROM reading_plans
                    ORDER BY name ASC
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows

    @staticmethod
    def get_plan_by_slug(slug: str) -> Optional[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, slug, name, description, duration_days, metadata
                    FROM reading_plans
                    WHERE LOWER(slug) = LOWER(%s)
                    LIMIT 1
                    """,
                    (slug,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                metadata = row.get("metadata")
                if isinstance(metadata, str):
                    row["metadata"] = json.loads(metadata)
                return row

    @staticmethod
    def get_plan_schedule(plan_id: int, max_days: Optional[int] = None) -> List[dict[str, Any]]:
        params: List[Any] = [plan_id]
        query = [
            "SELECT day_number, title, passage, notes, metadata",
            "FROM reading_plan_entries",
            "WHERE plan_id = %s",
            "ORDER BY day_number ASC",
        ]
        if max_days is not None:
            query.append("LIMIT %s")
            params.append(max_days)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("\n".join(query), tuple(params))
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows
