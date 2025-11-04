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
    def create_question(user_id: int, question: str, parent_question_id: int = None) -> int:
        """Create a new question and return its ID."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO questions (user_id, question, parent_question_id) VALUES (%s, %s, %s) RETURNING id;",
                    (user_id, question, parent_question_id)
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
    
    @staticmethod
    def get_root_question_id(question_id: int) -> int:
        """Get the root question ID for a given question (follows parent chain to root)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE root_finder AS (
                        -- Start with the given question
                        SELECT id, parent_question_id
                        FROM questions
                        WHERE id = %s
                        
                        UNION ALL
                        
                        -- Follow parent chain
                        SELECT q.id, q.parent_question_id
                        FROM questions q
                        JOIN root_finder rf ON q.id = rf.parent_question_id
                    )
                    SELECT id FROM root_finder WHERE parent_question_id IS NULL
                    """,
                    (question_id,)
                )
                result = cur.fetchone()
                return result['id'] if result else question_id
    
    @staticmethod
    def get_conversation_thread(question_id: int) -> list:
        """Get the full conversation thread for a question (root + all follow-ups)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Use recursive CTE to get entire conversation thread
                # Starting from the given question_id (which should be the root),
                # find all questions that have this as their parent
                cur.execute(
                    """
                    WITH RECURSIVE thread AS (
                        -- Base: start with the root question (the one with no parent or the given ID)
                        SELECT q.id, q.question, q.parent_question_id, q.asked_at, a.answer, 0 as depth
                        FROM questions q
                        LEFT JOIN answers a ON q.id = a.question_id
                        WHERE q.id = %s AND q.parent_question_id IS NULL
                        
                        UNION ALL
                        
                        -- Recursive: get all follow-up questions that reference items in the thread
                        SELECT q.id, q.question, q.parent_question_id, q.asked_at, a.answer, t.depth + 1
                        FROM questions q
                        JOIN thread t ON q.parent_question_id = t.id
                        LEFT JOIN answers a ON q.id = a.question_id
                    )
                    SELECT id, question, parent_question_id, asked_at, answer, depth
                    FROM thread
                    ORDER BY depth, asked_at
                    """,
                    (question_id,)
                )
                result = cur.fetchall()
                return result


class SavedAnswersRepository:
    """Repository for saved answers database operations."""
    
    @staticmethod
    def save_answer(user_id: int, question_id: int, tags: list) -> dict:
        """Save an answer for a user, using root question ID for conversations."""
        # Find the root question ID by following the parent chain
        root_question_id = QuestionRepository.get_root_question_id(question_id)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Save using the root question ID
                cur.execute(
                    """
                    INSERT INTO saved_answers (user_id, question_id, tags) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, question_id) DO UPDATE
                    SET tags = EXCLUDED.tags, saved_at = CURRENT_TIMESTAMP
                    RETURNING id, user_id, question_id, tags, saved_at
                    """,
                    (user_id, root_question_id, tags)
                )
                result = cur.fetchone()
                conn.commit()
                return result
    
    @staticmethod
    def get_user_saved_answers(user_id: int, limit: int = 100) -> list:
        """Get all saved answers for a user with question and answer details, including conversation threads."""
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
                        sa.saved_at,
                        q.parent_question_id
                    FROM saved_answers sa
                    JOIN questions q ON sa.question_id = q.id
                    LEFT JOIN answers a ON q.id = a.question_id
                    WHERE sa.user_id = %s
                    ORDER BY sa.saved_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )
                saved_answers = cur.fetchall()
                
                # For each saved answer, get the full conversation thread
                result = []
                for saved_answer in saved_answers:
                    thread = QuestionRepository.get_conversation_thread(saved_answer['question_id'])
                    result.append({
                        'id': saved_answer['id'],
                        'question_id': saved_answer['question_id'],
                        'question': saved_answer['question'],
                        'answer': saved_answer['answer'],
                        'tags': saved_answer['tags'],
                        'saved_at': saved_answer['saved_at'],
                        'parent_question_id': saved_answer['parent_question_id'],
                        'conversation_thread': thread
                    })
                
                return result
    
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
        """Search saved answers by query or tag, including conversation threads."""
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
                            sa.saved_at,
                            q.parent_question_id
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
                            sa.saved_at,
                            q.parent_question_id
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
                
                saved_answers = cur.fetchall()
                
                # For each saved answer, get the full conversation thread
                result = []
                for saved_answer in saved_answers:
                    thread = QuestionRepository.get_conversation_thread(saved_answer['question_id'])
                    result.append({
                        'id': saved_answer['id'],
                        'question_id': saved_answer['question_id'],
                        'question': saved_answer['question'],
                        'answer': saved_answer['answer'],
                        'tags': saved_answer['tags'],
                        'saved_at': saved_answer['saved_at'],
                        'parent_question_id': saved_answer['parent_question_id'],
                        'conversation_thread': thread
                    })
                
                return result
