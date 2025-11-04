"""Business logic for question handling."""
from app.services.openai_service import OpenAIService
from app.database import QuestionRepository
from app.models.schemas import (
    QuestionRequest, QuestionResponse, FollowUpQuestionRequest,
    HistoryResponse, HistoryItem
)
import logging

logger = logging.getLogger(__name__)


class QuestionService:
    """Service for handling question-related business logic."""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.question_repo = QuestionRepository()
    
    async def process_question(self, request: QuestionRequest) -> QuestionResponse:
        """Process a question through the complete pipeline."""
        try:
            # Get AI answer
            answer = await self.openai_service.get_bible_answer(request.question)
            
            # Store question and answer in database
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question
            )
            
            self.question_repo.create_answer(question_id, answer)
            
            return QuestionResponse(answer=answer, question_id=question_id)
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            raise
    
    async def process_followup_question(self, request: FollowUpQuestionRequest) -> QuestionResponse:
        """Process a follow-up question with conversation context."""
        try:
            # Convert conversation history to OpenAI format
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
            
            # Get AI answer with context
            answer = await self.openai_service.get_bible_answer(
                request.question,
                conversation_history=conversation_history
            )
            
            # Store question and answer in database with parent reference
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question,
                parent_question_id=request.parent_question_id
            )
            
            self.question_repo.create_answer(question_id, answer)
            
            return QuestionResponse(answer=answer, question_id=question_id)
            
        except Exception as e:
            logger.error(f"Error processing follow-up question: {e}")
            raise
    
    def get_user_history(self, user_id: int, limit: int = 10) -> HistoryResponse:
        """Get question history for a user."""
        try:
            history_data = self.question_repo.get_question_history(user_id, limit)
            
            history_items = [
                HistoryItem(
                    id=item["id"],
                    question=item["question"],
                    answer=item["answer"],
                    created_at=item["created_at"]
                )
                for item in history_data
            ]
            
            return HistoryResponse(
                questions=history_items,
                total=len(history_items)
            )
            
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            raise
