"""Tests for ReadingPlanTrackingService."""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch, Mock, MagicMock

from fastapi import HTTPException

from app.services.reading_plan_tracking_service import ReadingPlanTrackingService
from app.utils.exceptions import ValidationError


@pytest.fixture
def service():
    return ReadingPlanTrackingService()


def _sample_plan_row(**overrides):
    """Build a sample user plan row matching DB output."""
    base = {
        "id": 1, "user_id": 1, "plan_id": 10,
        "plan_slug": "30-day", "plan_name": "30 Day Plan",
        "plan_description": "Read the Bible in 30 days",
        "plan_duration_days": 30,
        "plan_metadata": {},
        "start_date": date(2025, 1, 1),
        "nickname": None, "is_active": True,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "completed_at": None,
        "completed_days": 0, "last_completed_day": 0,
    }
    base.update(overrides)
    return base


class TestListUserPlans:

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_returns_serialized_plans(self, mock_repo, service):
        mock_repo.list_user_plans.return_value = [_sample_plan_row()]

        result = service.list_user_plans(user_id=1)

        assert len(result) == 1
        assert result[0]["plan"]["slug"] == "30-day"
        assert result[0]["percent_complete"] == 0.0

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_empty_list(self, mock_repo, service):
        mock_repo.list_user_plans.return_value = []

        result = service.list_user_plans(user_id=1)

        assert result == []


class TestStartPlan:

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    @patch("app.services.reading_plan_tracking_service.ReadingPlanRepository")
    def test_start_plan_success_default_start_date(self, mock_plan_repo, mock_user_repo, service):
        mock_plan_repo.get_plan_by_slug.return_value = {
            "id": 10, "slug": "30-day", "name": "30 Day Plan",
            "description": "desc", "duration_days": 30, "metadata": {},
        }
        mock_user_repo.create_user_plan.return_value = _sample_plan_row()

        result = service.start_plan(user_id=1, plan_slug="30-day")

        assert result["plan"]["slug"] == "30-day"
        mock_user_repo.create_user_plan.assert_called_once()
        call_kwargs = mock_user_repo.create_user_plan.call_args[1]
        assert call_kwargs["start_date"] == date.today()

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    @patch("app.services.reading_plan_tracking_service.ReadingPlanRepository")
    def test_start_plan_success_explicit_start_date(self, mock_plan_repo, mock_user_repo, service):
        mock_plan_repo.get_plan_by_slug.return_value = {
            "id": 10, "slug": "30-day", "name": "30 Day Plan",
            "description": "desc", "duration_days": 30, "metadata": {},
        }
        mock_user_repo.create_user_plan.return_value = _sample_plan_row(
            start_date=date(2025, 6, 15)
        )

        result = service.start_plan(user_id=1, plan_slug="30-day", start_date="2025-06-15")

        assert result["plan"]["slug"] == "30-day"
        call_kwargs = mock_user_repo.create_user_plan.call_args[1]
        assert call_kwargs["start_date"] == date(2025, 6, 15)

    @patch("app.services.reading_plan_tracking_service.ReadingPlanRepository")
    def test_start_plan_not_found(self, mock_plan_repo, service):
        mock_plan_repo.get_plan_by_slug.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.start_plan(user_id=1, plan_slug="nonexistent")

        assert exc_info.value.status_code == 404


class TestDeletePlan:

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_delete_plan_success(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row()
        mock_repo.delete_plan.return_value = True

        service.delete_plan(user_id=1, user_plan_id=1)

        mock_repo.delete_plan.assert_called_once_with(1, 1)

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_delete_plan_not_found(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.delete_plan(user_id=1, user_plan_id=999)

        assert exc_info.value.status_code == 404

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_delete_plan_delete_fails(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row()
        mock_repo.delete_plan.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            service.delete_plan(user_id=1, user_plan_id=1)

        assert exc_info.value.status_code == 404


class TestGetUserPlanDetail:

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    @patch("app.services.reading_plan_tracking_service.ReadingPlanRepository")
    def test_success_with_schedule_and_completions(self, mock_plan_repo, mock_user_repo, service):
        plan_row = _sample_plan_row(plan_duration_days=3)
        mock_user_repo.get_user_plan.return_value = plan_row

        mock_plan_repo.get_plan_schedule.return_value = [
            {"day_number": 1, "title": "Day 1", "passages": ["Gen 1"]},
            {"day_number": 2, "title": "Day 2", "passages": ["Gen 2"]},
            {"day_number": 3, "title": "Day 3", "passages": ["Gen 3"]},
        ]

        mock_user_repo.get_completion_map.return_value = {
            1: {"completed_at": datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)},
            2: {"completed_at": datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)},
        }

        result = service.get_user_plan_detail(user_id=1, user_plan_id=1)

        assert "schedule" in result
        assert len(result["schedule"]) == 3
        assert result["schedule"][0]["is_complete"] is True
        assert result["schedule"][0]["completed_at"] is not None
        assert result["schedule"][0]["scheduled_date"] == "2025-01-01"
        assert result["schedule"][1]["is_complete"] is True
        assert result["schedule"][2]["is_complete"] is False
        assert result["schedule"][2]["completed_at"] is None
        assert result["start_date"] == "2025-01-01"

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_plan_not_found(self, mock_user_repo, service):
        mock_user_repo.get_user_plan.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.get_user_plan_detail(user_id=1, user_plan_id=999)

        assert exc_info.value.status_code == 404


class TestUpdateDayCompletion:

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_mark_day_complete(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row()
        mock_repo.upsert_day_completion.return_value = {
            "day_number": 5, "completed_at": datetime(2025, 1, 5, tzinfo=timezone.utc),
        }
        mock_repo.get_completion_stats.return_value = {"completed_days": 5, "last_completed_day": 5}

        result = service.update_day_completion(
            user_id=1, user_plan_id=1, day_number=5, is_complete=True,
        )

        assert result["is_complete"] is True
        assert result["completed_days"] == 5
        assert result["completed_at"] is not None
        mock_repo.upsert_day_completion.assert_called_once_with(1, 5)

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_mark_day_incomplete(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row()
        mock_repo.get_completion_stats.return_value = {"completed_days": 4, "last_completed_day": 4}

        result = service.update_day_completion(
            user_id=1, user_plan_id=1, day_number=5, is_complete=False,
        )

        assert result["is_complete"] is False
        assert result["completed_at"] is None
        mock_repo.delete_day_completion.assert_called_once_with(1, 5)

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_plan_not_found(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.update_day_completion(
                user_id=1, user_plan_id=999, day_number=1, is_complete=True,
            )

        assert exc_info.value.status_code == 404

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_day_number_out_of_range_high(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row(plan_duration_days=30)

        with pytest.raises(ValidationError):
            service.update_day_completion(
                user_id=1, user_plan_id=1, day_number=31, is_complete=True,
            )

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_day_number_out_of_range_low(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row(plan_duration_days=30)

        with pytest.raises(ValidationError):
            service.update_day_completion(
                user_id=1, user_plan_id=1, day_number=0, is_complete=True,
            )

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_all_days_completed_sets_plan_completed_at(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row(plan_duration_days=3)
        mock_repo.upsert_day_completion.return_value = {
            "day_number": 3, "completed_at": datetime(2025, 1, 3, tzinfo=timezone.utc),
        }
        mock_repo.get_completion_stats.return_value = {"completed_days": 3, "last_completed_day": 3}

        result = service.update_day_completion(
            user_id=1, user_plan_id=1, day_number=3, is_complete=True,
        )

        assert result["plan_completed_at"] is not None
        assert result["percent_complete"] == 100.0
        mock_repo.set_plan_completed_at.assert_called_once()
        # The first positional arg should be user_plan_id
        call_args = mock_repo.set_plan_completed_at.call_args
        assert call_args[0][0] == 1
        # The second positional arg should be a datetime (not None)
        assert isinstance(call_args[0][1], datetime)

    @patch("app.services.reading_plan_tracking_service.UserReadingPlanRepository")
    def test_incomplete_days_clears_plan_completed_at(self, mock_repo, service):
        mock_repo.get_user_plan.return_value = _sample_plan_row(plan_duration_days=3)
        mock_repo.get_completion_stats.return_value = {"completed_days": 2, "last_completed_day": 2}

        result = service.update_day_completion(
            user_id=1, user_plan_id=1, day_number=3, is_complete=False,
        )

        assert result["plan_completed_at"] is None
        mock_repo.set_plan_completed_at.assert_called_once_with(1, None)


class TestParseStartDate:

    def test_none_returns_today(self):
        result = ReadingPlanTrackingService._parse_start_date(None)
        assert result == date.today()

    def test_empty_string_returns_today(self):
        result = ReadingPlanTrackingService._parse_start_date("")
        assert result == date.today()

    def test_valid_iso_date_string(self):
        result = ReadingPlanTrackingService._parse_start_date("2025-06-15")
        assert result == date(2025, 6, 15)

    def test_invalid_date_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ReadingPlanTrackingService._parse_start_date("not-a-date")


class TestSerializeSummary:

    def test_full_row_with_all_fields(self):
        row = _sample_plan_row(
            completed_days=10,
            last_completed_day=10,
            nickname="My Plan",
            is_active=True,
            completed_at=None,
        )
        result = ReadingPlanTrackingService._serialize_summary(row)

        assert result["id"] == 1
        assert result["plan"]["slug"] == "30-day"
        assert result["plan"]["name"] == "30 Day Plan"
        assert result["plan"]["description"] == "Read the Bible in 30 days"
        assert result["plan"]["duration_days"] == 30
        assert result["plan"]["metadata"] == {}
        assert result["start_date"] == "2025-01-01"
        assert result["nickname"] == "My Plan"
        assert result["is_active"] is True
        assert result["created_at"] is not None
        assert result["completed_at"] is None
        assert result["completed_days"] == 10
        assert result["total_days"] == 30
        assert result["percent_complete"] == 33.33
        assert result["next_day_number"] == 11

    def test_row_with_minimal_fields(self):
        row = {
            "id": 5,
            "plan_slug": "7-day",
            "plan_name": "7 Day Plan",
            "plan_duration_days": 7,
        }
        result = ReadingPlanTrackingService._serialize_summary(row)

        assert result["id"] == 5
        assert result["plan"]["slug"] == "7-day"
        assert result["plan"]["name"] == "7 Day Plan"
        assert result["plan"]["description"] is None
        assert result["plan"]["duration_days"] == 7
        assert result["plan"]["metadata"] == {}
        assert result["completed_days"] == 0
        assert result["total_days"] == 7
        assert result["percent_complete"] == 0.0
        assert result["next_day_number"] == 1
        assert result["start_date"] is None
        assert result["nickname"] is None
        assert result["is_active"] is True
        assert result["created_at"] is None
        assert result["completed_at"] is None

    def test_completed_plan(self):
        row = _sample_plan_row(
            completed_days=30,
            last_completed_day=30,
            completed_at=datetime(2025, 1, 30, tzinfo=timezone.utc),
        )
        result = ReadingPlanTrackingService._serialize_summary(row)

        assert result["percent_complete"] == 100.0
        assert result["next_day_number"] is None
        assert result["completed_at"] is not None
