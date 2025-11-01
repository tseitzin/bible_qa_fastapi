"""Unit tests for the question service."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.question_service import QuestionService
from app.models.schemas import QuestionRequest, QuestionResponse, HistoryResponse, HistoryItem


class TestQuestionService:
    """Test cases for QuestionService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionService()
    
    @patch('app.services.question_service.OpenAIService')
    @patch('app.services.question_service.QuestionRepository')
    async def test_process_question_success(self, mock_repo_class, mock_openai_class):
        """Test successful question processing."""
        # Mock OpenAI service
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(
            return_value="Faith is the substance of things hoped for, the evidence of things not seen."
        )
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
        
        # Verify service calls
        mock_openai.get_bible_answer.assert_called_once_with("What is faith?")
        mock_repo.create_question.assert_called_once_with(user_id=1, question="What is faith?")
        mock_repo.create_answer.assert_called_once_with(123, "Faith is the substance of things hoped for, the evidence of things not seen.")
    
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
