"""Saved answers routes for managing user's saved Q&A."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Annotated, Optional
from app.models.schemas import SavedAnswerCreate, SavedAnswerResponse, SavedAnswersListResponse
from app.database import SavedAnswersRepository
from app.auth import get_current_user_dependency
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/saved-answers", tags=["saved-answers"])

CurrentUser = Annotated[dict, Depends(get_current_user_dependency)]


@router.post("", response_model=SavedAnswerResponse, status_code=status.HTTP_201_CREATED)
async def save_answer(
    data: SavedAnswerCreate,
    current_user: CurrentUser
):
    """Save an answer to user's collection."""
    try:
        result = SavedAnswersRepository.save_answer(
            user_id=current_user["id"],
            question_id=data.question_id,
            tags=data.tags
        )
        
        # Fetch the complete saved answer details
        saved_answers = SavedAnswersRepository.get_user_saved_answers(
            user_id=current_user["id"],
            limit=1
        )
        
        if not saved_answers:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve saved answer"
            )
        
        logger.info(f"User {current_user['id']} saved answer for question {data.question_id}")
        return saved_answers[0]
    
    except Exception as e:
        logger.error(f"Error saving answer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save answer"
        )


@router.get("", response_model=SavedAnswersListResponse)
async def get_saved_answers(
    current_user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    query: Optional[str] = Query(default=None, description="Search query"),
    tag: Optional[str] = Query(default=None, description="Filter by tag")
):
    """Get user's saved answers with optional search and filtering."""
    try:
        if query or tag:
            saved_answers = SavedAnswersRepository.search_saved_answers(
                user_id=current_user["id"],
                query=query,
                tag=tag
            )
        else:
            saved_answers = SavedAnswersRepository.get_user_saved_answers(
                user_id=current_user["id"],
                limit=limit
            )
        
        return {
            "saved_answers": saved_answers,
            "total": len(saved_answers)
        }
    
    except Exception as e:
        logger.error(f"Error retrieving saved answers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved answers"
        )


@router.delete("/{saved_answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_answer(
    saved_answer_id: int,
    current_user: CurrentUser
):
    """Delete a saved answer from user's collection."""
    try:
        deleted = SavedAnswersRepository.delete_saved_answer(
            user_id=current_user["id"],
            saved_answer_id=saved_answer_id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved answer not found"
            )
        
        logger.info(f"User {current_user['id']} deleted saved answer {saved_answer_id}")
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting saved answer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete saved answer"
        )


@router.get("/tags", response_model=list[str])
async def get_tags(current_user: CurrentUser):
    """Get all unique tags used by the user."""
    try:
        tags = SavedAnswersRepository.get_user_tags(user_id=current_user["id"])
        return tags
    except Exception as e:
        logger.error(f"Error retrieving tags: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tags"
        )
