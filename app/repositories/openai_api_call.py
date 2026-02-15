"""Repository for OpenAI API call tracking and analytics."""
import logging
from typing import Any, Dict, List, Optional

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class OpenAIApiCallRepository:
    """Repository for OpenAI API call tracking and analytics."""

    @staticmethod
    def log_call(
        user_id: Optional[int],
        question: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        status: str,
        error_message: Optional[str] = None,
        response_time_ms: Optional[int] = None,
    ) -> None:
        """Log an OpenAI API call."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO openai_api_calls
                        (user_id, question, model, prompt_tokens, completion_tokens,
                         total_tokens, status, error_message, response_time_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, question, model, prompt_tokens, completion_tokens,
                         total_tokens, status, error_message, response_time_ms)
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log OpenAI API call: {e}")

    @staticmethod
    def get_calls(
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get OpenAI API call logs with optional filters."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = [
                    "SELECT id, timestamp, user_id, question, model, prompt_tokens,",
                    "completion_tokens, total_tokens, status, error_message, response_time_ms",
                    "FROM openai_api_calls",
                    "WHERE 1=1"
                ]
                params: List[Any] = []

                if user_id is not None:
                    query.append("AND user_id = %s")
                    params.append(user_id)

                if status:
                    query.append("AND status = %s")
                    params.append(status)

                if start_date:
                    query.append("AND timestamp >= %s")
                    params.append(start_date)

                if end_date:
                    query.append("AND timestamp <= %s")
                    params.append(end_date)

                query.append("ORDER BY timestamp DESC")
                query.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])

                cur.execute(" ".join(query), tuple(params))
                return cur.fetchall()

    @staticmethod
    def get_usage_stats(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated OpenAI usage statistics."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        COUNT(*) as total_calls,
                        COUNT(DISTINCT user_id) as unique_users,
                        SUM(total_tokens) as total_tokens_used,
                        SUM(prompt_tokens) as total_prompt_tokens,
                        SUM(completion_tokens) as total_completion_tokens,
                        AVG(total_tokens) as avg_tokens_per_call,
                        AVG(response_time_ms) as avg_response_time_ms,
                        COUNT(*) FILTER (WHERE status = 'success') as successful_calls,
                        COUNT(*) FILTER (WHERE status = 'error') as error_calls,
                        COUNT(*) FILTER (WHERE status = 'rate_limit') as rate_limit_calls
                    FROM openai_api_calls
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
    def get_user_usage(
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """Get OpenAI usage statistics grouped by user."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """SELECT
                        user_id,
                        COUNT(*) as call_count,
                        SUM(total_tokens) as total_tokens,
                        AVG(total_tokens) as avg_tokens_per_call,
                        MAX(timestamp) as last_call
                    FROM openai_api_calls
                    WHERE user_id IS NOT NULL"""
                ]
                params: List[Any] = []

                if start_date:
                    query_parts.append("AND timestamp >= %s")
                    params.append(start_date)

                if end_date:
                    query_parts.append("AND timestamp <= %s")
                    params.append(end_date)

                query_parts.append("GROUP BY user_id")
                query_parts.append("ORDER BY total_tokens DESC")
                query_parts.append("LIMIT %s")
                params.append(limit)

                query = " ".join(query_parts)
                cur.execute(query, tuple(params))
                return cur.fetchall()
