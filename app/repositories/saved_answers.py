"""Repository for saved answers database operations."""
from app.database import get_db_connection
from app.repositories.question import QuestionRepository


class SavedAnswersRepository:
    """Repository for saved answers database operations."""

    @staticmethod
    def admin_delete_saved_answer(answer_id: int) -> bool:
        """Delete a saved answer by ID (admin, no user check)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM saved_answers WHERE id = %s",
                    (answer_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted

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
