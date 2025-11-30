"""Business logic for question handling."""
from app.services.openai_service import OpenAIService
from app.services.cache_service import CacheService
from app.database import QuestionRepository, RecentQuestionsRepository
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
    
    async def process_question(self, request: QuestionRequest, record_recent: bool = False) -> QuestionResponse:
        """Process a question through the complete pipeline."""
        try:
            # Check cache first for identical questions
            cached_answer = CacheService.get_question(request.question)
            if cached_answer:
                logger.info(f"Cache hit for question: {request.question[:50]}...")
                # Still store in database for history
                is_biblical = self.openai_service.is_biblical_answer(cached_answer)
                question_id = self.question_repo.create_question(
                    user_id=request.user_id,
                    question=request.question
                )
                self.question_repo.create_answer(question_id, cached_answer)
                
                if record_recent and is_biblical:
                    RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
                
                return QuestionResponse(answer=cached_answer, question_id=question_id, is_biblical=is_biblical)
            
            # Get AI answer
            answer = await self.openai_service.get_bible_answer(request.question)
            
            is_biblical = self.openai_service.is_biblical_answer(answer)

            # Store question and answer in database
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question
            )
            
            self.question_repo.create_answer(question_id, answer)
            
            # Cache the answer for future requests
            if is_biblical:  # Only cache biblical answers
                CacheService.set_question(request.question, answer)

            if record_recent and is_biblical:
                RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
            
            return QuestionResponse(answer=answer, question_id=question_id, is_biblical=is_biblical)
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            raise
    
    async def process_followup_question(self, request: FollowUpQuestionRequest, record_recent: bool = False) -> QuestionResponse:
        """Process a follow-up question with conversation context."""
        try:
            # Convert conversation history to OpenAI format
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
            
            # Check cache for this question with context
            cached_answer = CacheService.get_question(request.question, conversation_history)
            if cached_answer:
                logger.info(f"Cache hit for follow-up question: {request.question[:50]}...")
                # Still store in database for history
                is_biblical = self.openai_service.is_biblical_answer(cached_answer)
                question_id = self.question_repo.create_question(
                    user_id=request.user_id,
                    question=request.question,
                    parent_question_id=request.parent_question_id
                )
                self.question_repo.create_answer(question_id, cached_answer)
                
                if record_recent and is_biblical:
                    RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
                
                return QuestionResponse(answer=cached_answer, question_id=question_id, is_biblical=is_biblical)
            
            # Get AI answer with context
            answer = await self.openai_service.get_bible_answer(
                request.question,
                conversation_history=conversation_history
            )
            
            is_biblical = self.openai_service.is_biblical_answer(answer)

            # Store question and answer in database with parent reference
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question,
                parent_question_id=request.parent_question_id
            )
            
            self.question_repo.create_answer(question_id, answer)
            
            # Cache the answer for future requests with same context
            if is_biblical:  # Only cache biblical answers
                CacheService.set_question(request.question, answer, conversation_history)

            if record_recent and is_biblical:
                RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
            
            return QuestionResponse(answer=answer, question_id=question_id, is_biblical=is_biblical)
            
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
    
    async def stream_question(self, request: QuestionRequest, record_recent: bool = False):
        """Stream a question response, checking cache first.
        
        Yields:
            dict: Status updates and content chunks
                  {"type": "cached", "answer": str} for cached responses
                  {"type": "status", "message": str} for status updates
                  {"type": "content", "text": str} for streaming content
                  {"type": "done", "question_id": int} when complete
        """
        try:
            # Check cache first
            cached_answer = CacheService.get_question(request.question)
            if cached_answer:
                logger.info(f"Cache hit for streamed question: {request.question[:50]}...")
                
                # Return cached answer immediately (no streaming needed)
                is_biblical = self.openai_service.is_biblical_answer(cached_answer)
                question_id = self.question_repo.create_question(
                    user_id=request.user_id,
                    question=request.question
                )
                self.question_repo.create_answer(question_id, cached_answer)
                
                if record_recent and is_biblical:
                    RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
                
                # Yield complete cached response
                yield {"type": "cached", "answer": cached_answer, "question_id": question_id, "is_biblical": is_biblical}
                return
            
            # Stream from OpenAI
            complete_answer = ""
            async for chunk in self.openai_service.stream_bible_answer(request.question):
                if chunk["type"] == "content":
                    complete_answer += chunk["text"]
                yield chunk
            
            # After streaming completes, save and cache
            is_biblical = self.openai_service.is_biblical_answer(complete_answer)
            
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question
            )
            self.question_repo.create_answer(question_id, complete_answer)
            
            # Cache the complete answer
            if is_biblical:
                CacheService.set_question(request.question, complete_answer)
            
            if record_recent and is_biblical:
                RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
            
            # Yield completion event
            yield {"type": "done", "question_id": question_id, "is_biblical": is_biblical}
            
        except Exception as e:
            logger.error(f"Error streaming question: {e}")
            yield {"type": "error", "message": str(e)}
            raise
    
    async def stream_followup_question(self, request: FollowUpQuestionRequest, record_recent: bool = False):
        """Stream a follow-up question response with conversation context, checking cache first.
        
        Yields:
            dict: Status updates and content chunks
                  {"type": "cached", "answer": str} for cached responses
                  {"type": "status", "message": str} for status updates
                  {"type": "content", "text": str} for streaming content
                  {"type": "done", "question_id": int} when complete
        """
        try:
            # Convert conversation history to OpenAI format
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
            
            # Check cache first (includes conversation context)
            cached_answer = CacheService.get_question(request.question, conversation_history)
            if cached_answer:
                logger.info(f"Cache hit for streamed follow-up question: {request.question[:50]}...")
                
                # Return cached answer immediately (no streaming needed)
                is_biblical = self.openai_service.is_biblical_answer(cached_answer)
                question_id = self.question_repo.create_question(
                    user_id=request.user_id,
                    question=request.question,
                    parent_question_id=request.parent_question_id
                )
                self.question_repo.create_answer(question_id, cached_answer)
                
                if record_recent and is_biblical:
                    RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
                
                # Yield complete cached response
                yield {"type": "cached", "answer": cached_answer, "question_id": question_id, "is_biblical": is_biblical}
                return
            
            # Stream from OpenAI with conversation context
            complete_answer = ""
            async for chunk in self.openai_service.stream_bible_answer(
                request.question,
                conversation_history=conversation_history
            ):
                if chunk["type"] == "content":
                    complete_answer += chunk["text"]
                yield chunk
            
            # After streaming completes, save and cache
            is_biblical = self.openai_service.is_biblical_answer(complete_answer)
            
            question_id = self.question_repo.create_question(
                user_id=request.user_id,
                question=request.question,
                parent_question_id=request.parent_question_id
            )
            self.question_repo.create_answer(question_id, complete_answer)
            
            # Cache the complete answer with conversation context
            if is_biblical:
                CacheService.set_question(request.question, complete_answer, conversation_history)
            
            if record_recent and is_biblical:
                RecentQuestionsRepository.add_recent_question(request.user_id, request.question)
            
            # Yield completion event
            yield {"type": "done", "question_id": question_id, "is_biblical": is_biblical}
            
        except Exception as e:
            logger.error(f"Error streaming follow-up question: {e}")
            yield {"type": "error", "message": str(e)}
            raise
