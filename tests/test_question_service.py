"""Unit tests for the question service."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.question_service import QuestionService
from app.services.openai_service import NON_BIBLICAL_RESPONSE
from app.models.schemas import (
    QuestionRequest,
    QuestionResponse,
    FollowUpQuestionRequest,
    ConversationMessage,
    HistoryResponse,
    HistoryItem,
)


class TestQuestionService:
    """Test cases for QuestionService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionService()
    
    @pytest.mark.asyncio
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_success(self, mock_repo_class, mock_openai_class):
        """Test successful question processing."""
        # Mock OpenAI service
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(
            return_value="Faith is the substance of things hoped for, the evidence of things not seen."
        )
        mock_openai.is_biblical_answer.return_value = True
        mock_openai_class.return_value = mock_openai
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.create_question.return_value = 123
        mock_repo.create_answer.return_value = None
        mock_repo_class.return_value = mock_repo
        
        # Create new service instance with mocks
        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo
        
        # Test request
        request = QuestionRequest(
            question="What is faith?",
            user_id=1
        )
        
        result = await service.process_question(request)
        
        # Assertions
        assert isinstance(result, QuestionResponse)
        assert result.answer == "Faith is the substance of things hoped for, the evidence of things not seen."
        assert result.question_id == 123
        assert result.is_biblical is True
        
        # Verify service calls
        mock_openai.get_bible_answer.assert_called_once_with("What is faith?")
        mock_repo.create_question.assert_called_once_with(user_id=1, question="What is faith?")
        mock_repo.create_answer.assert_called_once_with(123, "Faith is the substance of things hoped for, the evidence of things not seen.")
    
    @pytest.mark.asyncio
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_openai_error(self, mock_repo_class, mock_openai_class):
        """Test question processing when OpenAI service fails."""
        # Mock OpenAI service to raise error
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )
        mock_openai_class.return_value = mock_openai
        
        # Mock repository
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        
        # Create service with mocks
        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo
        
        request = QuestionRequest(
            question="What is love?",
            user_id=1
        )
        
        # Should propagate the exception
        with pytest.raises(Exception, match="API rate limit exceeded"):
            await service.process_question(request)
        
        # Repository methods should not be called if OpenAI fails
        mock_repo.create_question.assert_not_called()
        mock_repo.create_answer.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_database_error(self, mock_repo_class, mock_openai_class):
        """Test question processing when database operation fails."""
        # Mock OpenAI service
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value="Test answer")
        mock_openai_class.return_value = mock_openai
        
        # Mock repository to raise error
        mock_repo = Mock()
        mock_repo.create_question.side_effect = Exception("Database connection failed")
        mock_repo_class.return_value = mock_repo
        
        # Create service with mocks
        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo
        
        request = QuestionRequest(
            question="What is hope?",
            user_id=1
        )
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Database connection failed"):
            await service.process_question(request)

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_records_recent_when_enabled(
        self,
        mock_repo_class,
        mock_openai_class,
        mock_add_recent,
    ):
        """Record_recent flag triggers recent questions repository update."""

        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value="Answer")
        mock_openai.is_biblical_answer.return_value = True
        mock_openai_class.return_value = mock_openai

        mock_repo = Mock()
        mock_repo.create_question.return_value = 55
        mock_repo_class.return_value = mock_repo

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="Tracked question", user_id=7)

        result = await service.process_question(request, record_recent=True)

        assert result.question_id == 55
        assert result.is_biblical is True
        mock_add_recent.assert_called_once_with(7, "Tracked question")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_skips_recent_for_non_biblical(
        self,
        mock_repo_class,
        mock_openai_class,
        mock_add_recent,
    ):
        """Refusal responses are not recorded as recent questions."""

        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value=NON_BIBLICAL_RESPONSE)
        mock_openai.is_biblical_answer.return_value = False
        mock_openai_class.return_value = mock_openai

        mock_repo = Mock()
        mock_repo.create_question.return_value = 44
        mock_repo_class.return_value = mock_repo

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="Tell me about space travel", user_id=3)

        result = await service.process_question(request, record_recent=True)

        assert result.question_id == 44
        assert result.is_biblical is False
        mock_add_recent.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_followup_question_success(self, mock_repo_class, mock_openai_class, mock_add_recent):
        """Test processing a follow-up question with conversation history."""
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value="Detailed follow-up answer")
        mock_openai.is_biblical_answer.return_value = True
        mock_openai_class.return_value = mock_openai

        mock_repo = Mock()
        mock_repo.create_question.return_value = 321
        mock_repo.create_answer.return_value = None
        mock_repo_class.return_value = mock_repo

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What happened after the Exodus?",
            user_id=2,
            parent_question_id=111,
            conversation_history=[
                ConversationMessage(role="user", content="Tell me about Moses."),
                ConversationMessage(role="assistant", content="Moses led Israel out of Egypt."),
            ]
        )

        result = await service.process_followup_question(request, record_recent=True)

        assert isinstance(result, QuestionResponse)
        assert result.question_id == 321
        assert result.is_biblical is True
        mock_openai.get_bible_answer.assert_called_once()
        called_args, called_kwargs = mock_openai.get_bible_answer.call_args
        assert called_args[0] == "What happened after the Exodus?"
        assert len(called_kwargs["conversation_history"]) == 2
        mock_repo.create_question.assert_called_once_with(
            user_id=2,
            question="What happened after the Exodus?",
            parent_question_id=111
        )
        mock_add_recent.assert_called_once_with(2, "What happened after the Exodus?")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_followup_question_skips_non_biblical_recent(
        self,
        mock_repo_class,
        mock_openai_class,
        mock_add_recent,
    ):
        """Non-biblical follow-up responses are not tracked as recent."""

        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value=NON_BIBLICAL_RESPONSE)
        mock_openai.is_biblical_answer.return_value = False
        mock_openai_class.return_value = mock_openai

        mock_repo = Mock()
        mock_repo.create_question.return_value = 222
        mock_repo.create_answer.return_value = None
        mock_repo_class.return_value = mock_repo

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What should I cook tonight?",
            user_id=5,
            parent_question_id=101,
            conversation_history=[],
        )

        result = await service.process_followup_question(request, record_recent=True)

        assert result.question_id == 222
        assert result.is_biblical is False
        mock_add_recent.assert_not_called()
    
    @patch('app.services.question_service.QuestionRepository')
    def test_get_user_history_success(self, mock_repo_class):
        """Test successful user history retrieval."""
        # Mock repository response
        mock_repo = Mock()
        mock_history_data = [
            {
                "id": 1,
                "question": "What is love?",
                "answer": "God is love.",
                "created_at": datetime(2025, 7, 31, 12, 0, 0)
            },
            {
                "id": 2,
                "question": "What is faith?",
                "answer": "Faith is believing.",
                "created_at": datetime(2025, 7, 31, 11, 0, 0)
            }
        ]
        mock_repo.get_question_history.return_value = mock_history_data
        mock_repo_class.return_value = mock_repo
        
        # Create service with mock
        service = QuestionService()
        service.question_repo = mock_repo
        
        result = service.get_user_history(user_id=1, limit=10)
        
        # Assertions
        assert isinstance(result, HistoryResponse)
        assert result.total == 2
        assert len(result.questions) == 2
        
        # Check first item
        first_item = result.questions[0]
        assert first_item.id == 1
        assert first_item.question == "What is love?"
        assert first_item.answer == "God is love."
        assert first_item.created_at == datetime(2025, 7, 31, 12, 0, 0)
        
        # Verify repository call
        mock_repo.get_question_history.assert_called_once_with(1, 10)
    
    @patch('app.services.question_service.QuestionRepository')
    def test_get_user_history_empty(self, mock_repo_class):
        """Test user history retrieval with no results."""
        # Mock empty repository response
        mock_repo = Mock()
        mock_repo.get_question_history.return_value = []
        mock_repo_class.return_value = mock_repo
        
        # Create service with mock
        service = QuestionService()
        service.question_repo = mock_repo
        
        result = service.get_user_history(user_id=999, limit=10)
        
        # Assertions
        assert isinstance(result, HistoryResponse)
        assert result.total == 0
        assert len(result.questions) == 0
    
    @patch('app.services.question_service.QuestionRepository')
    def test_get_user_history_database_error(self, mock_repo_class):
        """Test user history retrieval when database fails."""
        # Mock repository to raise error
        mock_repo = Mock()
        mock_repo.get_question_history.side_effect = Exception("Database timeout")
        mock_repo_class.return_value = mock_repo
        
        # Create service with mock
        service = QuestionService()
        service.question_repo = mock_repo
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Database timeout"):
            service.get_user_history(user_id=1, limit=10)


# Test fixtures
@pytest.fixture
def question_service():
    """Create a QuestionService instance for testing."""
    return QuestionService()


@pytest.fixture
def sample_question_request():
    """Sample question request."""
    return QuestionRequest(
        question="What does the Bible say about peace?",
        user_id=1
    )
