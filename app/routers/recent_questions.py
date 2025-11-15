"""Endpoints for managing a user's recent questions list."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.database import RecentQuestionsRepository
from app.models.schemas import (
    RecentQuestionCreate,
    RecentQuestionItem,
    RecentQuestionsResponse,
)


router = APIRouter(
    prefix="/api/users/me/recent-questions",
    tags=["recent-questions"],
)


@router.get("", response_model=RecentQuestionsResponse)
async def list_recent_questions(current_user: dict = Depends(get_current_user)):
    """Return the most recent questions asked by the authenticated user."""
    records = RecentQuestionsRepository.get_recent_questions(current_user["id"])
    recent_questions = [
        RecentQuestionItem(id=item["id"], question=item["question"], asked_at=item["asked_at"])
        for item in records
    ]
    return RecentQuestionsResponse(recent_questions=recent_questions)


@router.post("", response_model=RecentQuestionsResponse, status_code=status.HTTP_200_OK)
async def add_recent_question(
    payload: RecentQuestionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Explicitly record a recent question and return the updated list."""
    question_text = payload.question.strip()
    if not question_text:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    RecentQuestionsRepository.add_recent_question(current_user["id"], question_text)
    records = RecentQuestionsRepository.get_recent_questions(current_user["id"])
    recent_questions = [
        RecentQuestionItem(id=item["id"], question=item["question"], asked_at=item["asked_at"])
        for item in records
    ]
    return RecentQuestionsResponse(recent_questions=recent_questions)
