"""Tests for UserReadingPlanRepository."""
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from app.repositories.user_reading_plan import UserReadingPlanRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def _sample_plan_row(**overrides):
    base = {
        "id": 1, "user_id": 1, "plan_id": 10,
        "plan_slug": "30-day", "plan_name": "30 Day Plan",
        "plan_description": "desc", "plan_duration_days": 30,
        "plan_metadata": {}, "start_date": date(2025, 1, 1),
        "nickname": None, "is_active": True,
        "created_at": datetime(2025, 1, 1), "completed_at": None,
    }
    base.update(overrides)
    return base


class TestUserReadingPlanRepository:

    def test_normalize_metadata_dict(self):
        row = {"plan_metadata": {"k": "v"}}
        result = UserReadingPlanRepository._normalize_metadata(row)
        assert result["plan_metadata"] == {"k": "v"}

    def test_normalize_metadata_string(self):
        row = {"plan_metadata": '{"k": "v"}'}
        result = UserReadingPlanRepository._normalize_metadata(row)
        assert result["plan_metadata"] == {"k": "v"}

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_create_user_plan(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = _sample_plan_row()

        result = UserReadingPlanRepository.create_user_plan(
            user_id=1, plan_id=10, plan_slug="30-day",
            plan_name="30 Day Plan", plan_description="desc",
            plan_duration_days=30, plan_metadata={},
            start_date=date(2025, 1, 1), nickname=None,
        )

        assert result["id"] == 1
        conn.commit.assert_called_once()

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_list_user_plans(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        row = _sample_plan_row(completed_days=5, last_completed_day=5)
        cur.fetchall.return_value = [row]

        result = UserReadingPlanRepository.list_user_plans(user_id=1)

        assert len(result) == 1
        assert result[0]["id"] == 1

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_get_user_plan(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        row = _sample_plan_row(completed_days=3, last_completed_day=3)
        cur.fetchone.return_value = row

        result = UserReadingPlanRepository.get_user_plan(user_id=1, user_plan_id=1)

        assert result["id"] == 1

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_get_user_plan_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = UserReadingPlanRepository.get_user_plan(user_id=1, user_plan_id=999)

        assert result is None

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_get_completion_map(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"day_number": 1, "completed_at": datetime(2025, 1, 1), "notes": None},
            {"day_number": 2, "completed_at": datetime(2025, 1, 2), "notes": "Good read"},
        ]

        result = UserReadingPlanRepository.get_completion_map(user_plan_id=1)

        assert 1 in result
        assert 2 in result
        assert result[2]["notes"] == "Good read"

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_upsert_day_completion(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"day_number": 5, "completed_at": datetime(2025, 1, 5)}

        result = UserReadingPlanRepository.upsert_day_completion(user_plan_id=1, day_number=5)

        assert result["day_number"] == 5
        conn.commit.assert_called_once()

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_delete_day_completion_success(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 1}

        result = UserReadingPlanRepository.delete_day_completion(user_plan_id=1, day_number=3)

        assert result is True
        conn.commit.assert_called_once()

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_delete_day_completion_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = UserReadingPlanRepository.delete_day_completion(user_plan_id=1, day_number=99)

        assert result is False

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_get_completion_stats(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"completed_days": 10, "last_completed_day": 10}

        result = UserReadingPlanRepository.get_completion_stats(user_plan_id=1)

        assert result["completed_days"] == 10

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_get_completion_stats_empty(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = UserReadingPlanRepository.get_completion_stats(user_plan_id=999)

        assert result == {"completed_days": 0, "last_completed_day": 0}

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_set_plan_completed_at(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)

        UserReadingPlanRepository.set_plan_completed_at(user_plan_id=1, completed_at=datetime(2025, 2, 1))

        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_delete_plan_success(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {"id": 1}

        result = UserReadingPlanRepository.delete_plan(user_id=1, user_plan_id=1)

        assert result is True
        conn.commit.assert_called_once()

    @patch("app.repositories.user_reading_plan.get_db_connection")
    def test_delete_plan_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = UserReadingPlanRepository.delete_plan(user_id=1, user_plan_id=999)

        assert result is False
