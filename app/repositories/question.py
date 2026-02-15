"""Repository for question-related database operations."""
from app.database import get_db_connection


class QuestionRepository:
    """Repository for question-related database operations."""

    @staticmethod
    def delete_question(question_id: int) -> bool:
        """Delete a question and its answers by question ID."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete answers first (if any)
                cur.execute(
                    "DELETE FROM answers WHERE question_id = %s",
                    (question_id,)
                )
                # Delete the question itself
                cur.execute(
                    "DELETE FROM questions WHERE id = %s",
                    (question_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted

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
