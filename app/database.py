"""Database connection and operations."""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            cursor_factory=RealDictCursor
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


class QuestionRepository:
    """Repository for question-related database operations."""
    
    @staticmethod
    def create_question(user_id: int, question: str) -> int:
        """Create a new question and return its ID."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO questions (user_id, question) VALUES (%s, %s) RETURNING id;",
                    (user_id, question)
                )
                question_id = cur.fetchone()["id"]
                conn.commit()
                return question_id
    
    @staticmethod
    def create_answer(question_id: int, answer: str) -> None:
        """Create an answer for a question."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO answers (question_id, answer) VALUES (%s, %s);",
                    (question_id, answer)
                )
                conn.commit()
    
    @staticmethod
    def get_question_history(user_id: int, limit: int = 10) -> list:
        """Get recent questions for a user."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT q.id, q.question, q.asked_at, a.answer
                    FROM questions q
                    LEFT JOIN answers a ON q.id = a.question_id
                    WHERE q.user_id = %s
                    ORDER BY q.asked_at DESC
                    LIMIT %s
                """, (user_id, limit))
                return cur.fetchall()
