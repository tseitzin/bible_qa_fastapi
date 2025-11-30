"""Database connection and operations."""
import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

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


class QuestionRepository:
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


class UserNotesRepository:
    """Repository for storing and retrieving user-authored study notes."""

    @staticmethod
    def create_note(
        user_id: int,
        content: str,
        question_id: int | None = None,
        metadata: dict | None = None,
        source: str | None = None,
    ) -> dict:
        """Persist a note linked to an optional question reference."""
        metadata_json = json.dumps(metadata) if metadata is not None else None

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_notes (user_id, question_id, content, metadata, source)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING id, user_id, question_id, content, metadata, source, created_at, updated_at
                    """,
                    (user_id, question_id, content, metadata_json, source),
                )
                note = cur.fetchone()
                conn.commit()
                if note and isinstance(note.get("metadata"), str):
                    note["metadata"] = json.loads(note["metadata"])
                return note

    @staticmethod
    def list_notes(user_id: int, question_id: int | None = None, limit: int = 50) -> list:
        """Return notes for a user filtered by question when provided."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = [
                    "SELECT id, user_id, question_id, content, metadata, source, created_at, updated_at",
                    "FROM user_notes",
                    "WHERE user_id = %s",
                ]
                params: list[Any] = [user_id]

                if question_id is not None:
                    query.append("AND question_id = %s")
                    params.append(question_id)

                query.append("ORDER BY created_at DESC LIMIT %s")
                params.append(limit)

                cur.execute("\n".join(query), tuple(params))
                rows = cur.fetchall()
                for row in rows:
                    if isinstance(row.get("metadata"), str):
                        row["metadata"] = json.loads(row["metadata"])
                return rows


class CrossReferenceRepository:
    """Read-only access to Treasury of Scripture Knowledge cross references."""

    @staticmethod
    def get_cross_references(book: str, chapter: int, verse: int) -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT reference_data
                    FROM cross_references
                    WHERE LOWER(book) = LOWER(%s)
                      AND chapter = %s
                      AND verse = %s
                    LIMIT 1
                    """,
                    (book, chapter, verse),
                )
                row = cur.fetchone()
                data = row["reference_data"] if row else []
                if isinstance(data, str):
                    return json.loads(data)
                return data


class LexiconRepository:
    """Repository for lexical lookup data (Strong's style)."""

    @staticmethod
    def get_entry(strongs_number: Optional[str] = None, lemma: Optional[str] = None) -> Optional[dict[str, Any]]:
        if not strongs_number and not lemma:
            return None

        query = [
            "SELECT strongs_number, lemma, transliteration, pronunciation, language, definition, usage, reference_list, metadata",
            "FROM lexicon_entries",
        ]
        clauses: List[str] = []
        params: List[Any] = []

        if strongs_number:
            clauses.append("LOWER(strongs_number) = LOWER(%s)")
            params.append(strongs_number)

        if lemma:
            clauses.append("lemma ILIKE %s")
            params.append(f"%{lemma}%")

        if clauses:
            query.append("WHERE " + " AND ".join(clauses))

        query.append("ORDER BY created_at ASC LIMIT 1")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("\n".join(query), tuple(params))
                row = cur.fetchone()
                if not row:
                    return None

                references = row.pop("reference_list", [])
                metadata = row.get("metadata")
                if isinstance(references, str):
                    references = json.loads(references)
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                    row["metadata"] = metadata
                row["references"] = references
                return row


class TopicIndexRepository:
    """Repository for topical Bible study entries."""

    @staticmethod
    def search_topics(keyword: Optional[str] = None, limit: int = 10) -> List[dict[str, Any]]:
        pattern = f"%{keyword}%" if keyword else "%"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT topic, summary, keywords, reference_entries
                    FROM topic_index
                    WHERE topic ILIKE %s
                       OR summary ILIKE %s
                       OR EXISTS (
                            SELECT 1 FROM unnest(keywords) kw WHERE kw ILIKE %s
                       )
                    ORDER BY topic ASC
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, limit),
                )
                rows = cur.fetchall()
                for row in rows:
                    keywords = row.get("keywords")
                    if keywords is None:
                        row["keywords"] = []
                    else:
                        row["keywords"] = list(keywords)
                    references = row.pop("reference_entries", [])
                    if isinstance(references, str):
                        references = json.loads(references)
                    row["references"] = references
                return rows


class ReadingPlanRepository:
    """Repository backing curated reading plans."""

    @staticmethod
    def list_plans() -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, slug, name, description, duration_days, metadata
                    FROM reading_plans
                    ORDER BY name ASC
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows

    @staticmethod
    def get_plan_by_slug(slug: str) -> Optional[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, slug, name, description, duration_days, metadata
                    FROM reading_plans
                    WHERE LOWER(slug) = LOWER(%s)
                    LIMIT 1
                    """,
                    (slug,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                metadata = row.get("metadata")
                if isinstance(metadata, str):
                    row["metadata"] = json.loads(metadata)
                return row

    @staticmethod
    def get_plan_schedule(plan_id: int, max_days: Optional[int] = None) -> List[dict[str, Any]]:
        params: List[Any] = [plan_id]
        query = [
            "SELECT day_number, title, passage, notes, metadata",
            "FROM reading_plan_entries",
            "WHERE plan_id = %s",
            "ORDER BY day_number ASC",
        ]
        if max_days is not None:
            query.append("LIMIT %s")
            params.append(max_days)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("\n".join(query), tuple(params))
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows


class DevotionalTemplateRepository:
    """Repository for devotional scaffolding templates."""

    @staticmethod
    def list_templates() -> List[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slug, title, body, prompt_1, prompt_2, default_passage, metadata
                    FROM devotional_templates
                    ORDER BY title ASC
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    metadata = row.get("metadata")
                    if isinstance(metadata, str):
                        row["metadata"] = json.loads(metadata)
                return rows

    @staticmethod
    def get_template(slug: str) -> Optional[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slug, title, body, prompt_1, prompt_2, default_passage, metadata
                    FROM devotional_templates
                    WHERE LOWER(slug) = LOWER(%s)
                    LIMIT 1
                    """,
                    (slug,),
                )
                template = cur.fetchone()
                if not template:
                    return None
                metadata = template.get("metadata")
                if isinstance(metadata, str):
                    template["metadata"] = json.loads(metadata)
                return template


class UserReadingPlanRepository:
    """Repository for user-specific reading plan instances and progress."""

    SUMMARY_FIELDS = (
        "id, user_id, plan_id, plan_slug, plan_name, plan_description, plan_duration_days, "
        "plan_metadata, start_date, nickname, is_active, created_at, completed_at"
    )

    @staticmethod
    def _normalize_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = row.get("plan_metadata")
        if isinstance(metadata, str):
            row["plan_metadata"] = json.loads(metadata)
        return row

    @classmethod
    def create_user_plan(
        cls,
        *,
        user_id: int,
        plan_id: int,
        plan_slug: str,
        plan_name: str,
        plan_description: Optional[str],
        plan_duration_days: int,
        plan_metadata: Optional[Dict[str, Any]],
        start_date,
        nickname: Optional[str],
    ) -> Dict[str, Any]:
        metadata_json = json.dumps(plan_metadata or {})
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO user_reading_plans
                        (user_id, plan_id, plan_slug, plan_name, plan_description, plan_duration_days,
                         plan_metadata, start_date, nickname)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING {cls.SUMMARY_FIELDS}
                    """,
                    (
                        user_id,
                        plan_id,
                        plan_slug,
                        plan_name,
                        plan_description,
                        plan_duration_days,
                        metadata_json,
                        start_date,
                        nickname,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
            return cls._normalize_metadata(dict(row))

    @classmethod
    def list_user_plans(cls, user_id: int) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH progress AS (
                        SELECT user_plan_id,
                               COUNT(*) AS completed_days,
                               COALESCE(MAX(day_number), 0) AS last_completed_day
                        FROM user_reading_plan_days
                        GROUP BY user_plan_id
                    )
                    SELECT {cls.SUMMARY_FIELDS},
                           COALESCE(progress.completed_days, 0) AS completed_days,
                           COALESCE(progress.last_completed_day, 0) AS last_completed_day
                    FROM user_reading_plans upr
                    LEFT JOIN progress ON progress.user_plan_id = upr.id
                    WHERE upr.user_id = %s
                    ORDER BY upr.created_at DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return [cls._normalize_metadata(dict(row)) for row in rows]

    @classmethod
    def get_user_plan(cls, user_id: int, user_plan_id: int) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH progress AS (
                        SELECT user_plan_id,
                               COUNT(*) AS completed_days,
                               COALESCE(MAX(day_number), 0) AS last_completed_day
                        FROM user_reading_plan_days
                        WHERE user_plan_id = %s
                        GROUP BY user_plan_id
                    )
                    SELECT {cls.SUMMARY_FIELDS},
                           COALESCE(progress.completed_days, 0) AS completed_days,
                           COALESCE(progress.last_completed_day, 0) AS last_completed_day
                    FROM user_reading_plans upr
                    LEFT JOIN progress ON progress.user_plan_id = upr.id
                    WHERE upr.user_id = %s AND upr.id = %s
                    LIMIT 1
                    """,
                    (user_plan_id, user_id, user_plan_id),
                )
                row = cur.fetchone()
        if not row:
            return None
        return cls._normalize_metadata(dict(row))

    @staticmethod
    def get_completion_map(user_plan_id: int) -> Dict[int, Dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT day_number, completed_at, notes
                    FROM user_reading_plan_days
                    WHERE user_plan_id = %s
                    ORDER BY day_number ASC
                    """,
                    (user_plan_id,)
                )
                rows = cur.fetchall()
        return {row["day_number"]: row for row in rows}

    @staticmethod
    def upsert_day_completion(user_plan_id: int, day_number: int) -> Dict[str, Any]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_reading_plan_days (user_plan_id, day_number, completed_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_plan_id, day_number)
                    DO UPDATE SET completed_at = EXCLUDED.completed_at
                    RETURNING day_number, completed_at
                    """,
                    (user_plan_id, day_number),
                )
                row = cur.fetchone()
                conn.commit()
        return dict(row)

    @staticmethod
    def delete_day_completion(user_plan_id: int, day_number: int) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_reading_plan_days
                    WHERE user_plan_id = %s AND day_number = %s
                    RETURNING id
                    """,
                    (user_plan_id, day_number),
                )
                deleted = cur.fetchone() is not None
                conn.commit()
        return deleted

    @staticmethod
    def get_completion_stats(user_plan_id: int) -> Dict[str, Any]:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS completed_days,
                           COALESCE(MAX(day_number), 0) AS last_completed_day
                    FROM user_reading_plan_days
                    WHERE user_plan_id = %s
                    """,
                    (user_plan_id,)
                )
                row = cur.fetchone()
        return dict(row) if row else {"completed_days": 0, "last_completed_day": 0}

    @staticmethod
    def set_plan_completed_at(user_plan_id: int, completed_at: Optional[Any]) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE user_reading_plans
                    SET completed_at = %s,
                        is_active = CASE WHEN %s IS NULL THEN TRUE ELSE FALSE END
                    WHERE id = %s
                    """,
                    (completed_at, completed_at, user_plan_id),
                )
                conn.commit()

    @staticmethod
    def delete_plan(user_id: int, user_plan_id: int) -> bool:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_reading_plans
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                    """,
                    (user_plan_id, user_id),
                )
                deleted = cur.fetchone() is not None
                conn.commit()
        return deleted
