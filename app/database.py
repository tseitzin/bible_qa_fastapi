"""Database connection and operations."""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    settings = get_settings()
    conn = None
    try:
        # Use the db_config property which handles both Heroku and local configs
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
                # Use asked_at column from questions, alias to created_at for API schema compatibility
                cur.execute(
                    """
                    SELECT q.id, q.question, q.asked_at AS created_at, a.answer
                    FROM questions q
                    LEFT JOIN answers a ON q.id = a.question_id
                    WHERE q.user_id = %s
                    ORDER BY q.asked_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                return cur.fetchall()


class SavedAnswersRepository:
    """Repository for saved answers database operations."""
    
    @staticmethod
    def save_answer(user_id: int, question_id: int, tags: list) -> dict:
        """Save an answer for a user."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO saved_answers (user_id, question_id, tags) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, question_id) DO UPDATE
                    SET tags = EXCLUDED.tags, saved_at = CURRENT_TIMESTAMP
                    RETURNING id, user_id, question_id, tags, saved_at
                    """,
                    (user_id, question_id, tags)
                )
                result = cur.fetchone()
                conn.commit()
                return result
    
    @staticmethod
    def get_user_saved_answers(user_id: int, limit: int = 100) -> list:
        """Get all saved answers for a user with question and answer details."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        sa.id,
                        sa.question_id,
                        q.question,
                        a.answer,
                        sa.tags,
                        sa.saved_at
                    FROM saved_answers sa
                    JOIN questions q ON sa.question_id = q.id
                    LEFT JOIN answers a ON q.id = a.question_id
                    WHERE sa.user_id = %s
                    ORDER BY sa.saved_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                return cur.fetchall()
    
    @staticmethod
    def delete_saved_answer(user_id: int, saved_answer_id: int) -> bool:
        """Delete a saved answer for a user."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM saved_answers WHERE id = %s AND user_id = %s",
                    (saved_answer_id, user_id)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
    
    @staticmethod
    def get_user_tags(user_id: int) -> list:
        """Get all unique tags used by a user."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT unnest(tags) as tag
                    FROM saved_answers
                    WHERE user_id = %s
                    ORDER BY tag
                    """,
                    (user_id,)
                )
                return [row["tag"] for row in cur.fetchall()]
    
    @staticmethod
    def search_saved_answers(user_id: int, query: str = None, tag: str = None) -> list:
        """Search saved answers by query or tag."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if tag:
                    cur.execute(
                        """
                        SELECT 
                            sa.id,
                            sa.question_id,
                            q.question,
                            a.answer,
                            sa.tags,
                            sa.saved_at
                        FROM saved_answers sa
                        JOIN questions q ON sa.question_id = q.id
                        LEFT JOIN answers a ON q.id = a.question_id
                        WHERE sa.user_id = %s AND %s = ANY(sa.tags)
                        ORDER BY sa.saved_at DESC
                        """,
                        (user_id, tag)
                    )
                elif query:
                    search_pattern = f"%{query}%"
                    cur.execute(
                        """
                        SELECT 
                            sa.id,
                            sa.question_id,
                            q.question,
                            a.answer,
                            sa.tags,
                            sa.saved_at
                        FROM saved_answers sa
                        JOIN questions q ON sa.question_id = q.id
                        LEFT JOIN answers a ON q.id = a.question_id
                        WHERE sa.user_id = %s 
                        AND (q.question ILIKE %s OR a.answer ILIKE %s)
                        ORDER BY sa.saved_at DESC
                        """,
                        (user_id, search_pattern, search_pattern)
                    )
                else:
                    return SavedAnswersRepository.get_user_saved_answers(user_id)
                
                return cur.fetchall()
