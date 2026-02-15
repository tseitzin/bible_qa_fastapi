"""Repository for API request logging and analytics."""
import logging
from typing import Any, Dict, List, Optional

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class ApiRequestLogRepository:
    """Repository for API request logging and analytics."""

    @staticmethod
    def log_request(
        user_id: Optional[int],
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: Optional[str] = None,
        payload_summary: Optional[str] = None,
        country_code: Optional[str] = None,
        country_name: Optional[str] = None,
        city: Optional[str] = None,
    ) -> None:
        """Log an API request with optional geolocation data."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO api_request_logs
                        (user_id, endpoint, method, status_code, ip_address, payload_summary,
                         country_code, country_name, city)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, endpoint, method, status_code, ip_address, payload_summary,
                         country_code, country_name, city)
                    )
                    conn.commit()
        except Exception as e:
            # Don't break the app if logging fails
            logger.error(f"Failed to log API request: {e}")

    @staticmethod
    def get_logs(
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get API request logs with optional filters."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = [
                    "SELECT id, timestamp, user_id, endpoint, method, status_code, ip_address, payload_summary",
                    "FROM api_request_logs",
                    "WHERE 1=1"
                ]
                params: List[Any] = []

                if user_id is not None:
                    query.append("AND user_id = %s")
                    params.append(user_id)

                if endpoint:
                    query.append("AND endpoint ILIKE %s")
                    params.append(f"%{endpoint}%")

                if status_code is not None:
                    query.append("AND status_code = %s")
                    params.append(status_code)

                if start_date:
                    query.append("AND timestamp >= %s")
                    params.append(start_date)

                if end_date:
                    query.append("AND timestamp <= %s")
                    params.append(end_date)

                query.append("ORDER BY timestamp DESC")
                query.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])

                cur.execute(" ".join(query), params)
                return cur.fetchall()

    @staticmethod
    def get_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated statistics about API usage."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        COUNT(*) as total_requests,
                        COUNT(DISTINCT user_id) as unique_users,
                        COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 300) as successful_requests,
                        COUNT(*) FILTER (WHERE status_code >= 400) as error_requests,
                        COUNT(*) FILTER (WHERE endpoint LIKE '/api/ask%') as openai_requests
                    FROM api_request_logs
                    WHERE 1=1"""
                ]
                params: List[Any] = []

                if start_date:
                    query_parts.append("AND timestamp >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND timestamp <= %s")
                    params.append(end_date)

                query = " ".join(query_parts)
                cur.execute(query, tuple(params) if params else None)
                result = cur.fetchone()
                return result if result else {}

    @staticmethod
    def get_endpoint_stats(
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get statistics grouped by endpoint."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = [
                    """
                    SELECT
                        endpoint,
                        COUNT(*) as request_count,
                        AVG(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) * 100 as success_rate
                    FROM api_request_logs
                    WHERE 1=1
                    """
                ]
                params: List[Any] = []

                if start_date:
                    query.append("AND timestamp >= %s")
                    params.append(start_date)

                if end_date:
                    query.append("AND timestamp <= %s")
                    params.append(end_date)

                query.append("GROUP BY endpoint")
                query.append("ORDER BY request_count DESC")
                query.append("LIMIT %s")
                params.append(limit)

                cur.execute(" ".join(query), params)
                return cur.fetchall()
