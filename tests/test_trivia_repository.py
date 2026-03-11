"""Unit tests for TriviaRepository — all DB I/O mocked via get_db_connection."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

# Import app.main first to resolve the circular import that exists when
# importing app.repositories.trivia in isolation (app.repositories.__init__
# → api_request_log → database → api_request_log).
import app.main  # noqa: F401

from app.repositories.trivia import TriviaRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn_cursor(fetchone_return=None, fetchall_return=None):
    """Return (mock_conn, mock_cursor) with context-manager support."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_return
    mock_cursor.fetchall.return_value = fetchall_return or []

    mock_conn = MagicMock()
    # cursor() is used as a context manager: `with conn.cursor(...) as cur`
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def _patch_db(mock_conn):
    """Return a patch context for get_db_connection that yields mock_conn."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_conn)
    ctx.__exit__ = MagicMock(return_value=False)
    return patch("app.repositories.trivia.get_db_connection", return_value=ctx)


# ===========================================================================
# create_question
# ===========================================================================

class TestCreateQuestion:
    def test_returns_id_on_success(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 7})
        with _patch_db(mock_conn):
            result = TriviaRepository.create_question(
                question_text="Who built the ark?",
                question_type="multiple_choice",
                category="old_testament",
                difficulty="easy",
                options=["Noah", "Moses", "Abraham", "David"],
                correct_answer="Noah",
                correct_index=0,
                explanation="Genesis 6",
                scripture_reference="Genesis 6:14",
            )
        assert result == 7

    def test_returns_none_on_duplicate(self):
        """ON CONFLICT DO NOTHING → fetchone returns None → method returns None."""
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            result = TriviaRepository.create_question(
                question_text="Who built the ark?",
                question_type="multiple_choice",
                category="old_testament",
                difficulty="easy",
                options=["Noah", "Moses"],
                correct_answer="Noah",
                correct_index=0,
                explanation=None,
                scripture_reference="Genesis 6:14",
            )
        assert result is None

    def test_commits_transaction(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 1})
        with _patch_db(mock_conn):
            TriviaRepository.create_question(
                question_text="Q",
                question_type="multiple_choice",
                category="new_testament",
                difficulty="medium",
                options=["A", "B"],
                correct_answer="A",
                correct_index=0,
                explanation=None,
                scripture_reference=None,
            )
        mock_conn.commit.assert_called_once()

    def test_options_serialised_as_json(self):
        """Options list must be JSON-encoded before being sent to psycopg2."""
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 2})
        with _patch_db(mock_conn):
            TriviaRepository.create_question(
                question_text="Q",
                question_type="multiple_choice",
                category="old_testament",
                difficulty="hard",
                options=["Alpha", "Beta", "Gamma", "Delta"],
                correct_answer="Alpha",
                correct_index=0,
                explanation="Some explanation",
                scripture_reference="Rev 1:1",
            )
        # The 5th positional param to execute() is the JSON-encoded options
        call_args = mock_cursor.execute.call_args[0][1]
        assert call_args[4] == json.dumps(["Alpha", "Beta", "Gamma", "Delta"])


# ===========================================================================
# get_questions_for_round
# ===========================================================================

class TestGetQuestionsForRound:
    def test_returns_list_of_dicts(self):
        row = {"id": 1, "question_text": "Q?", "category": "old_testament"}
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[row])
        with _patch_db(mock_conn):
            result = TriviaRepository.get_questions_for_round("old_testament", "easy", 5)
        assert result == [dict(row)]

    def test_uses_exclude_ids_branch(self):
        """When exclude_ids is provided the query must contain NOT IN."""
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_questions_for_round(
                "new_testament", "medium", 3, exclude_ids=[10, 20]
            )
        sql = mock_cursor.execute.call_args[0][0]
        assert "NOT IN" in sql

    def test_no_exclude_ids_uses_simple_branch(self):
        """Without exclude_ids the simpler query branch must be used."""
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_questions_for_round("psalms_proverbs", "hard", 5)
        sql = mock_cursor.execute.call_args[0][0]
        assert "NOT IN" not in sql

    def test_returns_empty_list_when_no_rows(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            result = TriviaRepository.get_questions_for_round("old_testament", "easy", 5)
        assert result == []


# ===========================================================================
# get_question_by_id
# ===========================================================================

class TestGetQuestionById:
    def test_returns_dict_when_found(self):
        row = {"id": 3, "question_text": "Test?", "correct_answer": "A"}
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=row)
        with _patch_db(mock_conn):
            result = TriviaRepository.get_question_by_id(3)
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            result = TriviaRepository.get_question_by_id(9999)
        assert result is None

    def test_queries_by_correct_id(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 5, "question_text": "Q"})
        with _patch_db(mock_conn):
            TriviaRepository.get_question_by_id(5)
        params = mock_cursor.execute.call_args[0][1]
        assert params == (5,)


# ===========================================================================
# count_available_questions
# ===========================================================================

class TestCountAvailableQuestions:
    def test_returns_integer_count(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"cnt": 42})
        with _patch_db(mock_conn):
            result = TriviaRepository.count_available_questions("old_testament", "easy")
        assert result == 42

    def test_returns_zero_when_empty(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"cnt": 0})
        with _patch_db(mock_conn):
            result = TriviaRepository.count_available_questions("doctrine_theology", "hard")
        assert result == 0

    def test_passes_category_and_difficulty_to_query(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"cnt": 10})
        with _patch_db(mock_conn):
            TriviaRepository.count_available_questions("new_testament", "medium")
        params = mock_cursor.execute.call_args[0][1]
        assert params == ("new_testament", "medium")


# ===========================================================================
# increment_questions_usage
# ===========================================================================

class TestIncrementQuestionsUsage:
    def test_executes_update_for_each_entry(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        updates = [
            {"question_id": 1, "is_correct": True},
            {"question_id": 2, "is_correct": False},
        ]
        with _patch_db(mock_conn):
            TriviaRepository.increment_questions_usage(updates)
        assert mock_cursor.execute.call_count == 2

    def test_correct_answer_increments_times_correct(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.increment_questions_usage(
                [{"question_id": 10, "is_correct": True}]
            )
        params = mock_cursor.execute.call_args[0][1]
        # First param is the is_correct_increment (1 for correct)
        assert params[0] == 1

    def test_wrong_answer_does_not_increment_times_correct(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.increment_questions_usage(
                [{"question_id": 11, "is_correct": False}]
            )
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == 0

    def test_commits_after_all_updates(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.increment_questions_usage(
                [{"question_id": 1, "is_correct": True}]
            )
        mock_conn.commit.assert_called_once()

    def test_empty_list_does_nothing(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.increment_questions_usage([])
        mock_cursor.execute.assert_not_called()


# ===========================================================================
# get_daily_challenge
# ===========================================================================

class TestGetDailyChallenge:
    def test_returns_dict_when_found(self):
        row = {"id": 20, "question_text": "Daily Q?", "is_daily_challenge": True}
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=row)
        with _patch_db(mock_conn):
            result = TriviaRepository.get_daily_challenge("2026-01-01")
        assert result == dict(row)

    def test_returns_none_when_not_found(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            result = TriviaRepository.get_daily_challenge("2026-01-01")
        assert result is None

    def test_passes_date_to_query(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            TriviaRepository.get_daily_challenge("2026-03-10")
        params = mock_cursor.execute.call_args[0][1]
        assert params == ("2026-03-10",)


# ===========================================================================
# set_daily_challenge
# ===========================================================================

class TestSetDailyChallenge:
    def test_executes_update_and_commits(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.set_daily_challenge(question_id=5, date_str="2026-03-10")
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_passes_correct_params(self):
        mock_conn, mock_cursor = _make_conn_cursor()
        with _patch_db(mock_conn):
            TriviaRepository.set_daily_challenge(question_id=42, date_str="2026-06-15")
        params = mock_cursor.execute.call_args[0][1]
        # SQL is: UPDATE ... SET ... WHERE id = %s with (date_str, question_id)
        assert "2026-06-15" in params
        assert 42 in params


# ===========================================================================
# create_game_session
# ===========================================================================

class TestCreateGameSession:
    def test_returns_session_id(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 99})
        with _patch_db(mock_conn):
            result = TriviaRepository.create_game_session(
                user_id=1,
                category="old_testament",
                difficulty="easy",
                question_count=10,
                score=500,
                correct_count=7,
                time_taken_seconds=120,
                streak_max=4,
                is_daily_challenge=False,
                daily_date=None,
                answers=[],
            )
        assert result == 99

    def test_commits_after_insert(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 1})
        with _patch_db(mock_conn):
            TriviaRepository.create_game_session(
                user_id=2,
                category="new_testament",
                difficulty="medium",
                question_count=5,
                score=300,
                correct_count=3,
                time_taken_seconds=None,
                streak_max=2,
                is_daily_challenge=False,
                daily_date=None,
                answers=[{"question_id": 1}],
            )
        mock_conn.commit.assert_called_once()

    def test_answers_serialised_as_json(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"id": 55})
        answers = [{"question_id": 1, "is_correct": True}]
        with _patch_db(mock_conn):
            TriviaRepository.create_game_session(
                user_id=1,
                category="old_testament",
                difficulty="easy",
                question_count=1,
                score=100,
                correct_count=1,
                time_taken_seconds=10,
                streak_max=1,
                is_daily_challenge=True,
                daily_date="2026-03-10",
                answers=answers,
            )
        call_args = mock_cursor.execute.call_args[0][1]
        # Last param is the JSON-encoded answers
        assert call_args[-1] == json.dumps(answers)


# ===========================================================================
# get_leaderboard
# ===========================================================================

class TestGetLeaderboard:
    def test_returns_list_of_dicts(self):
        row = {"user_id": 1, "username": "alice", "best_score": 900}
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[row])
        with _patch_db(mock_conn):
            result = TriviaRepository.get_leaderboard(None, None, "all_time", 10)
        assert result == [dict(row)]

    def test_weekly_period_appended_to_query(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_leaderboard(None, None, "weekly", 5)
        sql = mock_cursor.execute.call_args[0][0]
        assert "7 days" in sql

    def test_all_time_period_no_interval_filter(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_leaderboard(None, None, "all_time", 5)
        sql = mock_cursor.execute.call_args[0][0]
        assert "7 days" not in sql

    def test_category_filter_appended(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_leaderboard("old_testament", None, "all_time", 10)
        params = mock_cursor.execute.call_args[0][1]
        assert "old_testament" in params

    def test_difficulty_filter_appended(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            TriviaRepository.get_leaderboard(None, "hard", "all_time", 10)
        params = mock_cursor.execute.call_args[0][1]
        assert "hard" in params

    def test_returns_empty_list_when_no_rows(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchall_return=[])
        with _patch_db(mock_conn):
            result = TriviaRepository.get_leaderboard(None, None, "all_time", 10)
        assert result == []


# ===========================================================================
# get_user_best_rank
# ===========================================================================

class TestGetUserBestRank:
    def test_returns_rank_when_found(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return={"rank": 3})
        with _patch_db(mock_conn):
            result = TriviaRepository.get_user_best_rank(1, None, None, "all_time")
        assert result == 3

    def test_returns_none_when_not_ranked(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            result = TriviaRepository.get_user_best_rank(99, None, None, "all_time")
        assert result is None

    def test_weekly_filter_in_query(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            TriviaRepository.get_user_best_rank(1, None, None, "weekly")
        sql = mock_cursor.execute.call_args[0][0]
        assert "7 days" in sql

    def test_category_and_difficulty_in_params(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            TriviaRepository.get_user_best_rank(1, "old_testament", "hard", "all_time")
        params = mock_cursor.execute.call_args[0][1]
        assert "old_testament" in params
        assert "hard" in params

    def test_user_id_always_last_param(self):
        mock_conn, mock_cursor = _make_conn_cursor(fetchone_return=None)
        with _patch_db(mock_conn):
            TriviaRepository.get_user_best_rank(42, None, None, "all_time")
        params = mock_cursor.execute.call_args[0][1]
        # user_id is always the last param in the query
        assert params[-1] == 42
