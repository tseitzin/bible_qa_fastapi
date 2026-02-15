"""Tests for ReadingPlanRepository."""
import json
from unittest.mock import patch, MagicMock

from app.repositories.reading_plan import ReadingPlanRepository


def _setup_db(mock_get_conn):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestReadingPlanRepository:

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_list_plans(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"id": 1, "slug": "30-day", "name": "30 Day Plan", "description": "desc", "duration_days": 30, "metadata": {}},
        ]

        result = ReadingPlanRepository.list_plans()

        assert len(result) == 1
        assert result[0]["slug"] == "30-day"

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_list_plans_deserializes_metadata_string(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"id": 1, "slug": "s", "name": "N", "description": "d", "duration_days": 7, "metadata": '{"k": "v"}'},
        ]

        result = ReadingPlanRepository.list_plans()

        assert result[0]["metadata"] == {"k": "v"}

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_get_plan_by_slug(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = {
            "id": 1, "slug": "gospels", "name": "Gospels",
            "description": "desc", "duration_days": 30, "metadata": {},
        }

        result = ReadingPlanRepository.get_plan_by_slug("gospels")

        assert result["name"] == "Gospels"

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_get_plan_by_slug_not_found(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchone.return_value = None

        result = ReadingPlanRepository.get_plan_by_slug("nonexistent")

        assert result is None

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_get_plan_schedule(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = [
            {"day_number": 1, "title": "Day 1", "passage": "Gen 1", "notes": None, "metadata": {}},
            {"day_number": 2, "title": "Day 2", "passage": "Gen 2", "notes": None, "metadata": {}},
        ]

        result = ReadingPlanRepository.get_plan_schedule(plan_id=1)

        assert len(result) == 2
        assert result[0]["day_number"] == 1

    @patch("app.repositories.reading_plan.get_db_connection")
    def test_get_plan_schedule_with_max_days(self, mock_get_conn):
        conn, cur = _setup_db(mock_get_conn)
        cur.fetchall.return_value = []

        ReadingPlanRepository.get_plan_schedule(plan_id=1, max_days=5)

        sql = cur.execute.call_args[0][0]
        assert "LIMIT" in sql
