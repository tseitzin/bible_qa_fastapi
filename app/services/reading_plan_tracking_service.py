"""Business logic for user reading plan tracking."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.database import ReadingPlanRepository, UserReadingPlanRepository
from app.utils.exceptions import ValidationError


class ReadingPlanTrackingService:
    """Coordinates storage and retrieval of user-specific reading plan progress."""

    def list_user_plans(self, user_id: int) -> List[Dict[str, Any]]:
        rows = UserReadingPlanRepository.list_user_plans(user_id)
        return [self._serialize_summary(row) for row in rows]

    def start_plan(
        self,
        *,
        user_id: int,
        plan_slug: str,
        start_date: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> Dict[str, Any]:
        plan = ReadingPlanRepository.get_plan_by_slug(plan_slug)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reading plan not found")

        normalized_start = self._parse_start_date(start_date)
        cleaned_nickname = nickname.strip() if nickname else None

        row = UserReadingPlanRepository.create_user_plan(
            user_id=user_id,
            plan_id=plan["id"],
            plan_slug=plan["slug"],
            plan_name=plan["name"],
            plan_description=plan.get("description"),
            plan_duration_days=plan["duration_days"],
            plan_metadata=plan.get("metadata", {}),
            start_date=normalized_start,
            nickname=cleaned_nickname,
        )
        return self._serialize_summary(row)

    def delete_plan(self, *, user_id: int, user_plan_id: int) -> None:
        plan_row = UserReadingPlanRepository.get_user_plan(user_id, user_plan_id)
        if not plan_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked plan not found")

        deleted = UserReadingPlanRepository.delete_plan(user_id, user_plan_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked plan not found")

    def get_user_plan_detail(self, *, user_id: int, user_plan_id: int) -> Dict[str, Any]:
        plan_row = UserReadingPlanRepository.get_user_plan(user_id, user_plan_id)
        if not plan_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked plan not found")

        schedule = ReadingPlanRepository.get_plan_schedule(plan_row["plan_id"])
        completion_map = UserReadingPlanRepository.get_completion_map(user_plan_id)
        start_date_value = plan_row.get("start_date")

        detailed_schedule: List[Dict[str, Any]] = []
        for step in schedule:
            day_number = step["day_number"]
            scheduled_date = None
            if isinstance(start_date_value, date):
                scheduled_date = (start_date_value + timedelta(days=day_number - 1)).isoformat()
            completion = completion_map.get(day_number)
            completed_at = completion["completed_at"].isoformat() if completion and completion["completed_at"] else None
            item = {
                **step,
                "scheduled_date": scheduled_date,
                "is_complete": completion is not None,
                "completed_at": completed_at,
            }
            detailed_schedule.append(item)

        summary = self._serialize_summary(plan_row)
        summary.update(
            {
                "start_date": start_date_value.isoformat() if isinstance(start_date_value, date) else summary.get("start_date"),
                "schedule": detailed_schedule,
            }
        )
        return summary

    def update_day_completion(
        self,
        *,
        user_id: int,
        user_plan_id: int,
        day_number: int,
        is_complete: bool,
    ) -> Dict[str, Any]:
        plan_row = UserReadingPlanRepository.get_user_plan(user_id, user_plan_id)
        if not plan_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked plan not found")

        total_days = plan_row["plan_duration_days"]
        if day_number < 1 or day_number > total_days:
            raise ValidationError("day_number is out of range for this plan")

        completed_at = None
        if is_complete:
            upserted = UserReadingPlanRepository.upsert_day_completion(user_plan_id, day_number)
            completed_at = upserted["completed_at"].isoformat() if upserted.get("completed_at") else None
        else:
            UserReadingPlanRepository.delete_day_completion(user_plan_id, day_number)

        stats = UserReadingPlanRepository.get_completion_stats(user_plan_id)
        completed_days = int(stats.get("completed_days", 0))

        plan_completed_at_str: Optional[str] = None
        if completed_days >= total_days and total_days > 0:
            timestamp = datetime.now(timezone.utc)
            UserReadingPlanRepository.set_plan_completed_at(user_plan_id, timestamp)
            plan_completed_at_str = timestamp.isoformat()
        else:
            UserReadingPlanRepository.set_plan_completed_at(user_plan_id, None)

        percent_complete = (completed_days / total_days * 100) if total_days else 0

        return {
            "day_number": day_number,
            "is_complete": is_complete,
            "completed_at": completed_at,
            "completed_days": completed_days,
            "total_days": total_days,
            "percent_complete": round(percent_complete, 2),
            "plan_completed_at": plan_completed_at_str,
        }

    @staticmethod
    def _parse_start_date(raw_value: Optional[str]) -> date:
        if not raw_value:
            return date.today()
        try:
            return date.fromisoformat(raw_value)
        except ValueError as err:
            raise ValidationError("start_date must be YYYY-MM-DD") from err

    @staticmethod
    def _serialize_summary(row: Dict[str, Any]) -> Dict[str, Any]:
        plan_meta = {
            "slug": row["plan_slug"],
            "name": row["plan_name"],
            "description": row.get("plan_description"),
            "duration_days": row["plan_duration_days"],
            "metadata": row.get("plan_metadata", {}),
        }
        completed_days = int(row.get("completed_days", 0) or 0)
        total_days = plan_meta["duration_days"] or 0
        last_completed_day = int(row.get("last_completed_day", 0) or 0)
        next_day_number: Optional[int] = None
        if completed_days < total_days:
            next_day_number = max(last_completed_day + 1, 1)
            if next_day_number > total_days:
                next_day_number = total_days

        percent_complete = (completed_days / total_days * 100) if total_days else 0

        start_date_value = row.get("start_date")
        start_date_iso = start_date_value.isoformat() if isinstance(start_date_value, date) else None

        return {
            "id": row["id"],
            "plan": plan_meta,
            "start_date": start_date_iso,
            "nickname": row.get("nickname"),
            "is_active": row.get("is_active", True),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "completed_at": row.get("completed_at").isoformat() if row.get("completed_at") else None,
            "completed_days": completed_days,
            "total_days": total_days,
            "percent_complete": round(percent_complete, 2),
            "next_day_number": next_day_number,
        }


def get_reading_plan_tracking_service() -> ReadingPlanTrackingService:
    return ReadingPlanTrackingService()
