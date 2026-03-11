"""Repository for trivia-related database operations."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class TriviaRepository:
    """Repository for trivia questions and game session database operations."""

    @staticmethod
    def create_question(
        question_text: str,
        question_type: str,
        category: str,
        difficulty: str,
        options: List[str],
        correct_answer: str,
        correct_index: Optional[int],
        explanation: Optional[str],
        scripture_reference: Optional[str],
    ) -> Optional[int]:
        """Insert a new trivia question and return its ID, or None on duplicate."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO trivia_questions
                        (question_text, question_type, category, difficulty, options,
                         correct_answer, correct_index, explanation, scripture_reference)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (category, difficulty, scripture_reference)
                    WHERE scripture_reference IS NOT NULL
                    DO NOTHING
                    RETURNING id
                    """,
                    (
                        question_text,
                        question_type,
                        category,
                        difficulty,
                        json.dumps(options),
                        correct_answer,
                        correct_index,
                        explanation,
                        scripture_reference,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return row["id"] if row else None

    @staticmethod
    def get_questions_for_round(
        category: str,
        difficulty: str,
        count: int,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a random selection of questions for a game round."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if exclude_ids:
                    cur.execute(
                        """
                        SELECT * FROM trivia_questions
                        WHERE category = %s AND difficulty = %s
                          AND id NOT IN %s
                        ORDER BY times_used ASC, RANDOM()
                        LIMIT %s
                        """,
                        (category, difficulty, tuple(exclude_ids), count),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM trivia_questions
                        WHERE category = %s AND difficulty = %s
                        ORDER BY times_used ASC, RANDOM()
                        LIMIT %s
                        """,
                        (category, difficulty, count),
                    )
                return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_question_by_id(question_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single trivia question by its primary key."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM trivia_questions WHERE id = %s",
                    (question_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    @staticmethod
    def count_available_questions(category: str, difficulty: str) -> int:
        """Return the count of questions available for a given category and difficulty."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM trivia_questions
                    WHERE category = %s AND difficulty = %s
                    """,
                    (category, difficulty),
                )
                return int(cur.fetchone()["cnt"])

    @staticmethod
    def increment_questions_usage(updates: List[Dict[str, Any]]) -> None:
        """Increment usage and correct-answer counters for a list of questions.

        Each dict in `updates` must contain ``question_id`` and ``is_correct``.
        """
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for update in updates:
                    is_correct_increment = 1 if update["is_correct"] else 0
                    cur.execute(
                        """
                        UPDATE trivia_questions
                        SET times_used = times_used + 1,
                            times_correct = times_correct + %s
                        WHERE id = %s
                        """,
                        (is_correct_increment, update["question_id"]),
                    )
            conn.commit()

    @staticmethod
    def get_daily_challenge(date_str: str) -> Optional[Dict[str, Any]]:
        """Fetch the daily challenge question for a given date string (YYYY-MM-DD)."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM trivia_questions
                    WHERE daily_date = %s AND is_daily_challenge = true
                    LIMIT 1
                    """,
                    (date_str,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    @staticmethod
    def set_daily_challenge(question_id: int, date_str: str) -> None:
        """Mark an existing question as the daily challenge for a given date."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    UPDATE trivia_questions
                    SET is_daily_challenge = true, daily_date = %s
                    WHERE id = %s
                    """,
                    (date_str, question_id),
                )
                conn.commit()

    @staticmethod
    def create_game_session(
        user_id: int,
        category: str,
        difficulty: str,
        question_count: int,
        score: int,
        correct_count: int,
        time_taken_seconds: Optional[int],
        streak_max: int,
        is_daily_challenge: bool,
        daily_date: Optional[str],
        answers: List[Dict[str, Any]],
    ) -> int:
        """Persist a completed game session and return its ID."""
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO trivia_game_sessions
                        (user_id, category, difficulty, question_count, score,
                         correct_count, time_taken_seconds, streak_max,
                         is_daily_challenge, daily_date, answers)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        category,
                        difficulty,
                        question_count,
                        score,
                        correct_count,
                        time_taken_seconds,
                        streak_max,
                        is_daily_challenge,
                        daily_date,
                        json.dumps(answers),
                    ),
                )
                session_id: int = cur.fetchone()["id"]
                conn.commit()
                return session_id

    @staticmethod
    def get_leaderboard(
        category: Optional[str],
        difficulty: Optional[str],
        period: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Return leaderboard entries ordered by best score descending."""
        base_query = """
            SELECT u.id AS user_id, u.username,
                   MAX(s.score) AS best_score,
                   ROUND(AVG(s.correct_count::numeric / NULLIF(s.question_count, 0)) * 100, 1) AS avg_accuracy,
                   COUNT(*) AS total_games
            FROM trivia_game_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE u.is_guest = false
        """
        params: List[Any] = []

        if category:
            base_query += " AND s.category = %s"
            params.append(category)
        if difficulty:
            base_query += " AND s.difficulty = %s"
            params.append(difficulty)
        if period == "weekly":
            base_query += " AND s.completed_at >= (NOW() - INTERVAL '7 days')"

        base_query += """
            GROUP BY u.id, u.username
            ORDER BY best_score DESC
            LIMIT %s
        """
        params.append(limit)

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(base_query, params)
                return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_user_best_rank(
        user_id: int,
        category: Optional[str],
        difficulty: Optional[str],
        period: str,
    ) -> Optional[int]:
        """Return the 1-based leaderboard rank for a specific user, or None if unranked."""
        inner_where = "WHERE u.is_guest = false"
        params: List[Any] = []

        if category:
            inner_where += " AND s.category = %s"
            params.append(category)
        if difficulty:
            inner_where += " AND s.difficulty = %s"
            params.append(difficulty)
        if period == "weekly":
            inner_where += " AND s.completed_at >= (NOW() - INTERVAL '7 days')"

        params.append(user_id)

        query = f"""
            WITH ranked AS (
                SELECT u.id AS user_id,
                       MAX(s.score) AS best_score,
                       ROW_NUMBER() OVER (ORDER BY MAX(s.score) DESC) AS rank
                FROM trivia_game_sessions s
                JOIN users u ON s.user_id = u.id
                {inner_where}
                GROUP BY u.id
            )
            SELECT rank FROM ranked WHERE user_id = %s
        """

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return int(row["rank"]) if row else None
