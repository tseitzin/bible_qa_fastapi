"""Repository for managing the recent questions cache per user."""
from app.database import get_db_connection


class RecentQuestionsRepository:
    """Repository for managing the recent questions cache per user."""

    MAX_RECENT_QUESTIONS = 6

    @classmethod
    def add_recent_question(cls, user_id: int, question: str) -> None:
        """Record or refresh a recent question for the user and trim to the latest entries."""
        if not user_id or not question:
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recent_questions (user_id, question)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, question) DO UPDATE
                        SET asked_at = CURRENT_TIMESTAMP
                    RETURNING id;
                    """,
                    (user_id, question)
                )

                # Trim to the most recent entries only
                cur.execute(
                    """
                    DELETE FROM recent_questions
                    WHERE user_id = %s
                      AND id NOT IN (
                        SELECT id FROM recent_questions
                        WHERE user_id = %s
                        ORDER BY asked_at DESC
                        LIMIT %s
                      );
                    """,
                    (user_id, user_id, cls.MAX_RECENT_QUESTIONS)
                )

                conn.commit()

    @staticmethod
    def get_recent_questions(user_id: int, limit: int = None) -> list:
        """Retrieve the most recent questions for a user."""
        if not user_id:
            return []

        limit = limit or RecentQuestionsRepository.MAX_RECENT_QUESTIONS

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, question, asked_at
                    FROM recent_questions
                    WHERE user_id = %s
                    ORDER BY asked_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit)
                )
                return cur.fetchall()

    @staticmethod
    def clear_user_recent_questions(user_id: int) -> None:
        """Remove all recent question entries for a given user."""
        if not user_id:
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM recent_questions WHERE user_id = %s;",
                    (user_id,)
                )
                conn.commit()

    @staticmethod
    def delete_recent_question(user_id: int, recent_question_id: int) -> bool:
        """Delete a single recent question entry for the user."""
        if not user_id or not recent_question_id:
            return False

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM recent_questions WHERE id = %s AND user_id = %s;",
                    (recent_question_id, user_id)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
