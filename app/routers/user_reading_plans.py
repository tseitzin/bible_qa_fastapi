"""Routes for managing user-specific reading plan progress."""
from typing import List

from fastapi import APIRouter, Depends, Path, Response

from app.auth import get_current_user_dependency
from app.models.schemas import (
    UserReadingPlanCreate,
    UserReadingPlanSummary,
    UserReadingPlanDetailResponse,
    ReadingPlanDayCompletionUpdate,
    ReadingPlanDayCompletionStatus,
)
from app.services.reading_plan_tracking_service import (
    ReadingPlanTrackingService,
    get_reading_plan_tracking_service,
)

router = APIRouter(prefix="/api/user-reading-plans", tags=["reading-plan-tracking"])


@router.get("", response_model=List[UserReadingPlanSummary])
async def list_user_reading_plans(
    current_user=Depends(get_current_user_dependency),
    service: ReadingPlanTrackingService = Depends(get_reading_plan_tracking_service),
):
    return service.list_user_plans(current_user["id"])


@router.post("", response_model=UserReadingPlanSummary, status_code=201)
async def start_user_reading_plan(
    payload: UserReadingPlanCreate,
    current_user=Depends(get_current_user_dependency),
    service: ReadingPlanTrackingService = Depends(get_reading_plan_tracking_service),
):
    return service.start_plan(
        user_id=current_user["id"],
        plan_slug=payload.plan_slug,
        start_date=payload.start_date,
        nickname=payload.nickname,
    )


@router.get("/{user_plan_id}", response_model=UserReadingPlanDetailResponse)
async def get_user_reading_plan_detail(
    user_plan_id: int = Path(..., ge=1),
    current_user=Depends(get_current_user_dependency),
    service: ReadingPlanTrackingService = Depends(get_reading_plan_tracking_service),
):
    return service.get_user_plan_detail(user_id=current_user["id"], user_plan_id=user_plan_id)


@router.patch("/{user_plan_id}/days/{day_number}", response_model=ReadingPlanDayCompletionStatus)
async def update_user_reading_plan_day(
    payload: ReadingPlanDayCompletionUpdate,
    user_plan_id: int = Path(..., ge=1),
    day_number: int = Path(..., ge=1),
    current_user=Depends(get_current_user_dependency),
    service: ReadingPlanTrackingService = Depends(get_reading_plan_tracking_service),
):
    return service.update_day_completion(
        user_id=current_user["id"],
        user_plan_id=user_plan_id,
        day_number=day_number,
        is_complete=payload.is_complete,
    )


@router.delete("/{user_plan_id}", status_code=204)
async def delete_user_reading_plan(
    user_plan_id: int = Path(..., ge=1),
    current_user=Depends(get_current_user_dependency),
    service: ReadingPlanTrackingService = Depends(get_reading_plan_tracking_service),
):
    service.delete_plan(user_id=current_user["id"], user_plan_id=user_plan_id)
    return Response(status_code=204)
