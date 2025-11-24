"""API routes for study resource utilities (cross references, topics, plans, devotionals)."""
from fastapi import APIRouter, Depends, Query
from typing import List

from app.models.schemas import (
    CrossReferenceResponse,
    TopicSearchResponse,
    ReadingPlanMeta,
    ReadingPlanDetailResponse,
    DevotionalTemplate,
    DevotionalRequest,
    GeneratedDevotionalResponse,
)
from app.services.study_resource_service import StudyResourceService, get_study_resource_service

router = APIRouter(prefix="/api/study", tags=["study"])


@router.get("/cross-references", response_model=CrossReferenceResponse)
async def get_cross_references(
    book: str = Query(..., min_length=2, description="Book name, e.g., 'John'"),
    chapter: int = Query(..., ge=1),
    verse: int = Query(..., ge=1),
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.get_cross_references(book, chapter, verse)


@router.get("/topics", response_model=TopicSearchResponse)
async def search_topics(
    keyword: str | None = Query(
        default=None,
        min_length=2,
        description="Optional keyword; omit to list featured topics",
    ),
    limit: int = Query(10, ge=1, le=50),
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.search_topics(keyword, limit)


@router.get("/reading-plans", response_model=List[ReadingPlanMeta])
async def list_reading_plans(
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.list_reading_plans()


@router.get("/reading-plans/{slug}", response_model=ReadingPlanDetailResponse)
async def get_reading_plan(
    slug: str,
    days: int | None = Query(default=None, ge=1, description="Optional day cap"),
    start_date: str | None = Query(default=None, description="ISO date for personalized schedule"),
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.get_reading_plan(slug, days=days, start_date=start_date)


@router.get("/devotional-templates", response_model=List[DevotionalTemplate])
async def list_devotional_templates(
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.list_devotional_templates()


@router.post("/devotionals", response_model=GeneratedDevotionalResponse)
async def generate_devotional(
    payload: DevotionalRequest,
    service: StudyResourceService = Depends(get_study_resource_service),
):
    return service.generate_devotional(
        topic=payload.topic,
        template_slug=payload.template_slug or "classic",
        passage=payload.passage,
        plan_slug=payload.plan_slug,
        day=payload.day,
    )
