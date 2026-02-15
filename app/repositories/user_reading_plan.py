"""Repository for user-specific reading plan instances and progress."""
import json
from typing import Any, Dict, List, Optional

from app.database import get_db_connection


class UserReadingPlanRepository:
    """Repository for user-specific reading plan instances and progress."""

    SUMMARY_FIELDS = (
        "id, user_id, plan_id, plan_slug, plan_name, plan_description, plan_duration_days, "
        "plan_metadata, start_date, nickname, is_active, created_at, completed_at"
    )

    @staticmethod
    def _normalize_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = row.get("plan_metadata")
        if isinstance(metadata, str):
            row["plan_metadata"] = json.loads(metadata)
        return row

    @classmethod
    def create_user_plan(
        cls,
        *,
        user_id: int,
        plan_id: int,
        plan_slug: str,
        plan_name: str,
        plan_description: Optional[str],
        plan_duration_days: int,
        plan_metadata: Optional[Dict[str, Any]],
        start_date,
        nickname: Optional[str],
    ) -> Dict[str, Any]:
        metadata_json = json.dumps(plan_metadata or {})
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO user_reading_plans
                        (user_id, plan_id, plan_slug, plan_name, plan_description, plan_duration_days,
                         plan_metadata, start_date, nickname)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING {cls.SUMMARY_FIELDS}
                    """,
                    (
                        user_id,
                        plan_id,
                        plan_slug,
                        plan_name,
                        plan_description,
                        plan_duration_days,
                        metadata_json,
                        start_date,
                        nickname,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
            return cls._normalize_metadata(dict(row))

    @classmethod
    def list_user_plans(cls, user_id: int) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH progress AS (
                        SELECT user_plan_id,
                               COUNT(*) AS completed_days,
                               COALESCE(MAX(day_number), 0) AS last_completed_day
                        FROM user_reading_plan_days
                        GROUP BY user_plan_id
                    )
                    SELECT {cls.SUMMARY_FIELDS},
                           COALESCE(progress.completed_days, 0) AS completed_days,
                           COALESCE(progress.last_completed_day, 0) AS last_completed_day
                    FROM user_reading_plans upr
                    LEFT JOIN progress ON progress.user_plan_id = upr.id
                    WHERE upr.user_id = %s
                    ORDER BY upr.created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [cls._normalize_metadata(dict(row)) for row in rows]

    @classmethod
    def get_user_plan(cls, user_id: int, user_plan_id: int) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH progress AS (
                        SELECT user_plan_id,
                               COUNT(*) AS completed_days,
                               COALESCE(MAX(day_number), 0) AS last_completed_day
                        FROM user_reading_plan_days
                        WHERE user_plan_id = %s
                        GROUP BY user_plan_id
                    )
                    SELECT {cls.SUMMARY_FIELDS},
                           COALESCE(progress.completed_days, 0) AS completed_days,
                           COALESCE(progress.last_completed_day, 0) AS last_completed_day
                    FROM user_reading_plans upr
                    LEFT JOIN progress ON progress.user_plan_id = upr.id
                    WHERE upr.user_id = %s AND upr.id = %s
                    LIMIT 1
                    """,
                    (user_plan_id, user_id, user_plan_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return cls._normalize_metadata(dict(row))

    @staticmethod
    def get_completion_map(user_plan_id: int) -> Dict[int, Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT day_number, completed_at, notes
                    FROM user_reading_plan_days
                    WHERE user_plan_id = %s
                    ORDER BY day_number ASC
                    """,
                    (user_plan_id,)
                )
                rows = cur.fetchall()
        return {row["day_number"]: row for row in rows}

    @staticmethod
    def upsert_day_completion(user_plan_id: int, day_number: int) -> Dict[str, Any]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_reading_plan_days (user_plan_id, day_number, completed_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_plan_id, day_number)
                    DO UPDATE SET completed_at = EXCLUDED.completed_at
                    RETURNING day_number, completed_at
                    """,
                    (user_plan_id, day_number),
                )
                row = cur.fetchone()
                conn.commit()
        return dict(row)

    @staticmethod
    def delete_day_completion(user_plan_id: int, day_number: int) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_reading_plan_days
                    WHERE user_plan_id = %s AND day_number = %s
                    RETURNING id
                    """,
                    (user_plan_id, day_number),
                )
                deleted = cur.fetchone() is not None
                conn.commit()
        return deleted

    @staticmethod
    def get_completion_stats(user_plan_id: int) -> Dict[str, Any]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS completed_days,
                           COALESCE(MAX(day_number), 0) AS last_completed_day
                    FROM user_reading_plan_days
                    WHERE user_plan_id = %s
                    """,
                    (user_plan_id,)
                )
                row = cur.fetchone()
        return dict(row) if row else {"completed_days": 0, "last_completed_day": 0}

    @staticmethod
    def set_plan_completed_at(user_plan_id: int, completed_at: Optional[Any]) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE user_reading_plans
                    SET completed_at = %s,
                        is_active = CASE WHEN %s IS NULL THEN TRUE ELSE FALSE END
                    WHERE id = %s
                    """,
                    (completed_at, completed_at, user_plan_id),
                )
                conn.commit()

    @staticmethod
    def delete_plan(user_id: int, user_plan_id: int) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_reading_plans
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                    """,
                    (user_plan_id, user_id),
                )
                deleted = cur.fetchone() is not None
                conn.commit()
        return deleted
