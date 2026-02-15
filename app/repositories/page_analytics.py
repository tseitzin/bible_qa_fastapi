"""Repository for page analytics and user behavior tracking."""
import logging
from typing import Any, Dict, List, Optional

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class PageAnalyticsRepository:
    """Repository for page analytics and user behavior tracking."""

    @staticmethod
    def log_page_view(
        user_id: Optional[int],
        session_id: str,
        page_path: str,
        page_title: Optional[str] = None,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        country_code: Optional[str] = None,
        country_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> int:
        """Log a page view and return the page_analytics_id."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO page_analytics
                        (user_id, session_id, page_path, page_title, referrer, user_agent,
                         ip_address, country_code, country_name, city)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (user_id, session_id, page_path, page_title, referrer, user_agent,
                         ip_address, country_code, country_name, city)
                    )
                    page_analytics_id = cur.fetchone()["id"]
                    conn.commit()
                    return page_analytics_id
        except Exception as e:
            logger.error(f"Failed to log page view: {e}")
            raise

    @staticmethod
    def update_page_metrics(
        page_analytics_id: int,
        visit_duration_seconds: Optional[int] = None,
        max_scroll_depth_percent: Optional[int] = None,
    ) -> None:
        """Update page metrics (scroll depth and duration)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Build dynamic update query
                    updates = []
                    params = []

                    if visit_duration_seconds is not None:
                        updates.append("visit_duration_seconds = %s")
                        params.append(visit_duration_seconds)

                    if max_scroll_depth_percent is not None:
                        updates.append("max_scroll_depth_percent = %s")
                        params.append(max_scroll_depth_percent)

                    if not updates:
                        return

                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(page_analytics_id)

                    query = f"UPDATE page_analytics SET {', '.join(updates)} WHERE id = %s"
                    cur.execute(query, params)
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to update page metrics: {e}")

    @staticmethod
    def log_click_event(
        page_analytics_id: Optional[int],
        user_id: Optional[int],
        session_id: str,
        page_path: str,
        element_type: Optional[str] = None,
        element_id: Optional[str] = None,
        element_text: Optional[str] = None,
        element_class: Optional[str] = None,
        click_position_x: Optional[int] = None,
        click_position_y: Optional[int] = None,
    ) -> int:
        """Log a click event and return the click_event_id."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO click_events
                        (page_analytics_id, user_id, session_id, page_path, element_type,
                         element_id, element_text, element_class, click_position_x, click_position_y)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (page_analytics_id, user_id, session_id, page_path, element_type,
                         element_id, element_text, element_class, click_position_x, click_position_y)
                    )
                    click_event_id = cur.fetchone()["id"]

                    # Update clicks_count on page_analytics if linked
                    if page_analytics_id:
                        cur.execute(
                            "UPDATE page_analytics SET clicks_count = clicks_count + 1 WHERE id = %s",
                            (page_analytics_id,)
                        )

                    conn.commit()
                    return click_event_id
        except Exception as e:
            logger.error(f"Failed to log click event: {e}")
            raise

    @staticmethod
    def get_page_views(
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        page_path: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get page view analytics with optional filters."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT id, user_id, session_id, page_path, page_title, referrer,
                       visit_duration_seconds, max_scroll_depth_percent, clicks_count,
                       country_code, country_name, city, ip_address, created_at, updated_at
                    FROM page_analytics
                    WHERE 1=1"""
                ]
                params: List[Any] = []

                if user_id is not None:
                    query_parts.append("AND user_id = %s")
                    params.append(user_id)

                if page_path:
                    query_parts.append("AND page_path = %s")
                    params.append(page_path)

                if start_date:
                    query_parts.append("AND created_at >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND created_at <= %s")
                    params.append(end_date)

                query_parts.append("ORDER BY created_at DESC")
                query_parts.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])

                query = " ".join(query_parts)
                cur.execute(query, params)
                return cur.fetchall()

    @staticmethod
    def get_page_analytics_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated page analytics statistics."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        COUNT(*) as total_page_views,
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(DISTINCT page_path) as unique_pages,
                        AVG(visit_duration_seconds) as avg_duration_seconds,
                        AVG(max_scroll_depth_percent) as avg_scroll_depth_percent,
                        SUM(clicks_count) as total_clicks
                    FROM page_analytics
                    WHERE 1=1"""
                ]
                params: List[Any] = []

                if start_date:
                    query_parts.append("AND created_at >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND created_at <= %s")
                    params.append(end_date)

                query = " ".join(query_parts)
                cur.execute(query, tuple(params) if params else None)
                result = cur.fetchone()
                return result if result else {}

    @staticmethod
    def get_page_path_stats(
        limit: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get statistics grouped by page path."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        page_path,
                        COUNT(*) as view_count,
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        AVG(visit_duration_seconds) as avg_duration_seconds,
                        AVG(max_scroll_depth_percent) as avg_scroll_depth_percent,
                        SUM(clicks_count) as total_clicks
                    FROM page_analytics
                    WHERE 1=1"""
                ]
                params: List[Any] = []

                if start_date:
                    query_parts.append("AND created_at >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND created_at <= %s")
                    params.append(end_date)

                query_parts.append("GROUP BY page_path")
                query_parts.append("ORDER BY view_count DESC")
                query_parts.append("LIMIT %s")
                params.append(limit)

                query = " ".join(query_parts)
                cur.execute(query, params)
                return cur.fetchall()

    @staticmethod
    def get_click_events(
        limit: int = 100,
        offset: int = 0,
        page_analytics_id: Optional[int] = None,
        user_id: Optional[int] = None,
        page_path: Optional[str] = None,
        element_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get click events with optional filters."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT id, page_analytics_id, user_id, session_id, page_path,
                       element_type, element_id, element_text, element_class,
                       click_position_x, click_position_y, created_at
                    FROM click_events
                    WHERE 1=1"""
                ]
                params: List[Any] = []

                if page_analytics_id is not None:
                    query_parts.append("AND page_analytics_id = %s")
                    params.append(page_analytics_id)

                if user_id is not None:
                    query_parts.append("AND user_id = %s")
                    params.append(user_id)

                if page_path:
                    query_parts.append("AND page_path = %s")
                    params.append(page_path)

                if element_type:
                    query_parts.append("AND element_type = %s")
                    params.append(element_type)

                if start_date:
                    query_parts.append("AND created_at >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND created_at <= %s")
                    params.append(end_date)

                query_parts.append("ORDER BY created_at DESC")
                query_parts.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])

                query = " ".join(query_parts)
                cur.execute(query, params)
                return cur.fetchall()

    @staticmethod
    def get_click_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get click statistics grouped by element type."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        element_type,
                        COUNT(*) as click_count,
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(DISTINCT page_path) as pages_affected
                    FROM click_events
                    WHERE element_type IS NOT NULL"""
                ]
                params: List[Any] = []

                if start_date:
                    query_parts.append("AND created_at >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND created_at <= %s")
                    params.append(end_date)

                query_parts.append("GROUP BY element_type")
                query_parts.append("ORDER BY click_count DESC")

                query = " ".join(query_parts)
                cur.execute(query, tuple(params) if params else None)
                return cur.fetchall()
