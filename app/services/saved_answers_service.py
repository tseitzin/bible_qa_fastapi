"""Service for admin operations on saved answers."""
import logging

from app.database import SavedAnswersRepository

logger = logging.getLogger(__name__)

class SavedAnswersService:
    """Service for admin saved answer operations."""
    def delete_saved_answer(self, answer_id: int) -> bool:
        try:
            return SavedAnswersRepository.admin_delete_saved_answer(answer_id)
        except Exception as e:
            logger.error(f"Error deleting saved answer: {e}")
            return False
