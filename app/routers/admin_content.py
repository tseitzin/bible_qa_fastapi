"""Admin endpoints for managing questions and saved answers."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_admin_user
from app.database import QuestionRepository, SavedAnswersRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-content"])


@router.delete("/questions/{question_id}")
async def admin_delete_question(question_id: int, current_admin: dict = Depends(get_current_admin_user)):
    """Delete a question by ID (admin only)."""
    try:
        deleted = QuestionRepository.delete_question(question_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Question not found")
        return {"status": "deleted", "question_id": question_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete question error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/saved_answers/{answer_id}")
async def admin_delete_saved_answer(answer_id: int, current_admin: dict = Depends(get_current_admin_user)):
    """Delete a saved answer by ID (admin only)."""
    try:
        deleted = SavedAnswersRepository.admin_delete_saved_answer(answer_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Saved answer not found")
        return {"status": "deleted", "answer_id": answer_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin delete saved answer error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
