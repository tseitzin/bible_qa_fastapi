"""Database connection pool management.

Repository classes have been extracted to app/repositories/.
They are re-exported here for backward compatibility.
"""
import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def initialize_connection_pool(minconn: int = 2, maxconn: int = 20) -> None:
    """Initialize the database connection pool.

    Args:
        minconn: Minimum number of connections to maintain
        maxconn: Maximum number of connections allowed
    """
    global _connection_pool

    if _connection_pool is not None:
        logger.warning("Connection pool already initialized")
        return

    settings = get_settings()
    db_config = settings.db_config

    try:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn,
            maxconn,
            cursor_factory=RealDictCursor,
            **db_config
        )
        logger.info(f"Database connection pool initialized (min={minconn}, max={maxconn})")
    except psycopg2.Error as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def close_connection_pool() -> None:
    """Close all connections in the pool."""
    global _connection_pool

    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_db_connection():
    """Context manager for database connections from the pool.

    If the pool is not initialized, falls back to creating a direct connection.
    """
    global _connection_pool

    # Fallback to direct connection if pool not initialized
    if _connection_pool is None:
        logger.warning("Connection pool not initialized, using direct connection")
        settings = get_settings()
        conn = None
        try:
            db_config = settings.db_config
            conn = psycopg2.connect(
                cursor_factory=RealDictCursor,
                **db_config
            )
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
        return

    # Use connection from pool
    conn = None
    try:
        conn = _connection_pool.getconn()
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            _connection_pool.putconn(conn)


# Backward-compatible re-exports from app.repositories
from app.repositories.question import QuestionRepository  # noqa: E402, F401
from app.repositories.saved_answers import SavedAnswersRepository  # noqa: E402, F401
from app.repositories.recent_questions import RecentQuestionsRepository  # noqa: E402, F401
from app.repositories.user_notes import UserNotesRepository  # noqa: E402, F401
from app.repositories.cross_reference import CrossReferenceRepository  # noqa: E402, F401
from app.repositories.lexicon import LexiconRepository  # noqa: E402, F401
from app.repositories.topic_index import TopicIndexRepository  # noqa: E402, F401
from app.repositories.reading_plan import ReadingPlanRepository  # noqa: E402, F401
from app.repositories.devotional_template import DevotionalTemplateRepository  # noqa: E402, F401
from app.repositories.user_reading_plan import UserReadingPlanRepository  # noqa: E402, F401
from app.repositories.api_request_log import ApiRequestLogRepository  # noqa: E402, F401
from app.repositories.openai_api_call import OpenAIApiCallRepository  # noqa: E402, F401
from app.repositories.page_analytics import PageAnalyticsRepository  # noqa: E402, F401
