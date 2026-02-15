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


class TestProcessQuestionCacheHit:
    """Test cases for process_question when the cache returns a hit."""

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_returns_cached_answer(self, mock_cache_get):
        """When cache returns an answer, it is used instead of calling OpenAI."""
        mock_cache_get.return_value = "Cached: God is love."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 10
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is love?", user_id=1)
        result = await service.process_question(request)

        assert isinstance(result, QuestionResponse)
        assert result.answer == "Cached: God is love."
        assert result.question_id == 10
        assert result.is_biblical is True

        # OpenAI should NOT be called for the answer
        mock_openai.get_bible_answer.assert_not_called()
        # But is_biblical_answer should still be called on the cached answer
        mock_openai.is_biblical_answer.assert_called_once_with("Cached: God is love.")

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_stores_to_database(self, mock_cache_get):
        """Cached answers are still persisted to the database for history."""
        mock_cache_get.return_value = "Cached answer about faith."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 20
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is faith?", user_id=5)
        await service.process_question(request)

        mock_repo.create_question.assert_called_once_with(user_id=5, question="What is faith?")
        mock_repo.create_answer.assert_called_once_with(20, "Cached answer about faith.")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_records_recent_when_biblical(self, mock_cache_get, mock_add_recent):
        """Cache hit with record_recent=True and biblical answer records the question."""
        mock_cache_get.return_value = "Cached biblical answer."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 30
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is hope?", user_id=8)
        result = await service.process_question(request, record_recent=True)

        assert result.is_biblical is True
        mock_add_recent.assert_called_once_with(8, "What is hope?")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_skips_recent_for_non_biblical(self, mock_cache_get, mock_add_recent):
        """Cache hit with non-biblical answer does not record as recent."""
        mock_cache_get.return_value = NON_BIBLICAL_RESPONSE

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = False

        mock_repo = Mock()
        mock_repo.create_question.return_value = 31
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is the weather?", user_id=9)
        result = await service.process_question(request, record_recent=True)

        assert result.is_biblical is False
        mock_add_recent.assert_not_called()


class TestProcessFollowupCacheHit:
    """Test cases for process_followup_question when the cache returns a hit."""

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_returns_cached_followup_answer(self, mock_cache_get):
        """Cached follow-up answer is returned without calling OpenAI."""
        mock_cache_get.return_value = "Cached follow-up about Exodus."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 40
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What happened next?",
            user_id=2,
            parent_question_id=100,
            conversation_history=[
                ConversationMessage(role="user", content="Tell me about the Exodus."),
                ConversationMessage(role="assistant", content="God led Israel out of Egypt."),
            ],
        )

        result = await service.process_followup_question(request)

        assert isinstance(result, QuestionResponse)
        assert result.answer == "Cached follow-up about Exodus."
        assert result.question_id == 40
        assert result.is_biblical is True

        mock_openai.get_bible_answer.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_passes_parent_question_id(self, mock_cache_get):
        """Cached follow-up correctly stores parent_question_id in the database."""
        mock_cache_get.return_value = "Cached answer with parent."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 41
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="Tell me more.",
            user_id=3,
            parent_question_id=200,
            conversation_history=[],
        )

        await service.process_followup_question(request)

        mock_repo.create_question.assert_called_once_with(
            user_id=3,
            question="Tell me more.",
            parent_question_id=200,
        )

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_passes_conversation_history_to_cache(self, mock_cache_get):
        """Cache lookup includes the conversation history for context-sensitive cache keys."""
        mock_cache_get.return_value = "Cached contextual answer."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 42
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        history = [
            ConversationMessage(role="user", content="Who was David?"),
            ConversationMessage(role="assistant", content="David was king of Israel."),
        ]

        request = FollowUpQuestionRequest(
            question="What did he do?",
            user_id=4,
            parent_question_id=300,
            conversation_history=history,
        )

        await service.process_followup_question(request)

        expected_history = [
            {"role": "user", "content": "Who was David?"},
            {"role": "assistant", "content": "David was king of Israel."},
        ]
        mock_cache_get.assert_called_once_with("What did he do?", expected_history)

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.get_question')
    async def test_cache_hit_records_recent_when_biblical(self, mock_cache_get, mock_add_recent):
        """Cached biblical follow-up records a recent question when flag is set."""
        mock_cache_get.return_value = "Cached biblical follow-up."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 43
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="And then what?",
            user_id=6,
            parent_question_id=400,
            conversation_history=[],
        )

        result = await service.process_followup_question(request, record_recent=True)

        assert result.is_biblical is True
        mock_add_recent.assert_called_once_with(6, "And then what?")


class TestProcessFollowupQuestionError:
    """Test cases for error propagation in process_followup_question."""

    @pytest.mark.asyncio
    async def test_openai_error_propagates(self):
        """Exception from OpenAI service propagates through follow-up processing."""
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(
            side_effect=Exception("OpenAI API timeout")
        )

        mock_repo = Mock()

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="Tell me more about Moses.",
            user_id=1,
            parent_question_id=50,
            conversation_history=[
                ConversationMessage(role="user", content="Who was Moses?"),
                ConversationMessage(role="assistant", content="Moses was a prophet."),
            ],
        )

        with pytest.raises(Exception, match="OpenAI API timeout"):
            await service.process_followup_question(request)

        mock_repo.create_question.assert_not_called()
        mock_repo.create_answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_database_error_propagates(self):
        """Exception from database operations propagates through follow-up processing."""
        mock_openai = Mock()
        mock_openai.get_bible_answer = AsyncMock(return_value="An answer")
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.side_effect = Exception("DB connection lost")

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What about the Psalms?",
            user_id=2,
            parent_question_id=60,
            conversation_history=[],
        )

        with pytest.raises(Exception, match="DB connection lost"):
            await service.process_followup_question(request)


class TestStreamQuestion:
    """Test cases for stream_question async generator."""

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_no_cache_hit(self, mock_cache_get, mock_cache_set):
        """Streaming with no cache hit yields chunks from OpenAI then a done event."""
        stream_chunks = [
            {"type": "content", "text": "God is "},
            {"type": "content", "text": "love."},
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in stream_chunks:
                yield chunk

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 50
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is love?", user_id=1)

        chunks = [c async for c in service.stream_question(request)]

        # Should yield the 2 content chunks + 1 done event
        assert len(chunks) == 3
        assert chunks[0] == {"type": "content", "text": "God is "}
        assert chunks[1] == {"type": "content", "text": "love."}
        assert chunks[2]["type"] == "done"
        assert chunks[2]["question_id"] == 50
        assert chunks[2]["is_biblical"] is True

        # Complete answer should be stored in DB
        mock_repo.create_question.assert_called_once_with(user_id=1, question="What is love?")
        mock_repo.create_answer.assert_called_once_with(50, "God is love.")

        # Biblical answer should be cached
        mock_cache_set.assert_called_once_with("What is love?", "God is love.")

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_no_cache_non_biblical_not_cached(self, mock_cache_get, mock_cache_set):
        """Non-biblical streamed answers are not cached."""
        async def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": NON_BIBLICAL_RESPONSE}

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = False

        mock_repo = Mock()
        mock_repo.create_question.return_value = 51
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is quantum physics?", user_id=1)

        chunks = [c async for c in service.stream_question(request)]

        assert chunks[-1]["type"] == "done"
        assert chunks[-1]["is_biblical"] is False
        mock_cache_set.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_stream_cache_hit(self, mock_cache_get):
        """When cache returns an answer, a single cached event is yielded."""
        mock_cache_get.return_value = "Cached streaming answer."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 60
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is grace?", user_id=3)

        chunks = [c async for c in service.stream_question(request)]

        assert len(chunks) == 1
        assert chunks[0]["type"] == "cached"
        assert chunks[0]["answer"] == "Cached streaming answer."
        assert chunks[0]["question_id"] == 60
        assert chunks[0]["is_biblical"] is True

        # Should still store to DB
        mock_repo.create_question.assert_called_once_with(user_id=3, question="What is grace?")
        mock_repo.create_answer.assert_called_once_with(60, "Cached streaming answer.")

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_error_handling(self, mock_cache_get):
        """Errors during streaming yield an error event and re-raise."""
        async def mock_stream(*args, **kwargs):
            raise Exception("Stream connection failed")
            yield  # noqa: unreachable — needed so Python treats this as async generator

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream

        mock_repo = Mock()

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is mercy?", user_id=1)

        with pytest.raises(Exception, match="Stream connection failed"):
            chunks = [c async for c in service.stream_question(request)]

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_record_recent_with_streaming(self, mock_cache_get, mock_cache_set, mock_add_recent):
        """Record_recent flag records the question after streaming completes."""
        async def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Streamed biblical answer."}

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 70
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is prayer?", user_id=4)

        chunks = [c async for c in service.stream_question(request, record_recent=True)]

        assert chunks[-1]["type"] == "done"
        mock_add_recent.assert_called_once_with(4, "What is prayer?")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.get_question')
    async def test_stream_cache_hit_records_recent(self, mock_cache_get, mock_add_recent):
        """Cache hit with record_recent=True records the question."""
        mock_cache_get.return_value = "Cached answer for recent."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 75
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="What is worship?", user_id=5)

        chunks = [c async for c in service.stream_question(request, record_recent=True)]

        assert len(chunks) == 1
        assert chunks[0]["type"] == "cached"
        mock_add_recent.assert_called_once_with(5, "What is worship?")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_non_biblical_skips_recent(self, mock_cache_get, mock_cache_set, mock_add_recent):
        """Non-biblical streamed answers do not record as recent even when flag is set."""
        async def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": NON_BIBLICAL_RESPONSE}

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = False

        mock_repo = Mock()
        mock_repo.create_question.return_value = 71
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = QuestionRequest(question="How do I fix my car?", user_id=4)

        chunks = [c async for c in service.stream_question(request, record_recent=True)]

        mock_add_recent.assert_not_called()


class TestStreamFollowupQuestion:
    """Test cases for stream_followup_question async generator."""

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_followup_no_cache_hit(self, mock_cache_get, mock_cache_set):
        """Streaming follow-up with no cache yields chunks then done event."""
        stream_chunks = [
            {"type": "content", "text": "After the flood, "},
            {"type": "content", "text": "God made a covenant."},
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in stream_chunks:
                yield chunk

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 80
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        history = [
            ConversationMessage(role="user", content="Tell me about Noah."),
            ConversationMessage(role="assistant", content="Noah built the ark."),
        ]

        request = FollowUpQuestionRequest(
            question="What happened after the flood?",
            user_id=2,
            parent_question_id=500,
            conversation_history=history,
        )

        chunks = [c async for c in service.stream_followup_question(request)]

        assert len(chunks) == 3
        assert chunks[0] == {"type": "content", "text": "After the flood, "}
        assert chunks[1] == {"type": "content", "text": "God made a covenant."}
        assert chunks[2]["type"] == "done"
        assert chunks[2]["question_id"] == 80
        assert chunks[2]["is_biblical"] is True

        # Verify parent_question_id is passed
        mock_repo.create_question.assert_called_once_with(
            user_id=2,
            question="What happened after the flood?",
            parent_question_id=500,
        )
        mock_repo.create_answer.assert_called_once_with(80, "After the flood, God made a covenant.")

        # Verify cache set is called with conversation history
        expected_history = [
            {"role": "user", "content": "Tell me about Noah."},
            {"role": "assistant", "content": "Noah built the ark."},
        ]
        mock_cache_set.assert_called_once_with(
            "What happened after the flood?",
            "After the flood, God made a covenant.",
            expected_history,
        )

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question')
    async def test_stream_followup_cache_hit(self, mock_cache_get):
        """When cache returns a follow-up answer, a single cached event is yielded."""
        mock_cache_get.return_value = "Cached follow-up stream answer."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 90
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="And what about his sons?",
            user_id=3,
            parent_question_id=600,
            conversation_history=[
                ConversationMessage(role="user", content="Tell me about Noah."),
                ConversationMessage(role="assistant", content="Noah had three sons."),
            ],
        )

        chunks = [c async for c in service.stream_followup_question(request)]

        assert len(chunks) == 1
        assert chunks[0]["type"] == "cached"
        assert chunks[0]["answer"] == "Cached follow-up stream answer."
        assert chunks[0]["question_id"] == 90
        assert chunks[0]["is_biblical"] is True

        # Verify DB storage with parent_question_id
        mock_repo.create_question.assert_called_once_with(
            user_id=3,
            question="And what about his sons?",
            parent_question_id=600,
        )

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_followup_error_handling(self, mock_cache_get):
        """Errors during follow-up streaming yield an error event and re-raise."""
        async def mock_stream(*args, **kwargs):
            raise Exception("Follow-up stream error")
            yield  # noqa: unreachable — needed so Python treats this as async generator

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream

        mock_repo = Mock()

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What else?",
            user_id=1,
            parent_question_id=700,
            conversation_history=[],
        )

        with pytest.raises(Exception, match="Follow-up stream error"):
            chunks = [c async for c in service.stream_followup_question(request)]

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_followup_records_recent(self, mock_cache_get, mock_cache_set, mock_add_recent):
        """Record_recent flag records follow-up question after streaming completes."""
        async def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Streamed follow-up answer."}

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 95
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="What about the Psalms?",
            user_id=7,
            parent_question_id=800,
            conversation_history=[],
        )

        chunks = [c async for c in service.stream_followup_question(request, record_recent=True)]

        assert chunks[-1]["type"] == "done"
        mock_add_recent.assert_called_once_with(7, "What about the Psalms?")

    @pytest.mark.asyncio
    @patch('app.services.question_service.RecentQuestionsRepository.add_recent_question')
    @patch('app.services.question_service.CacheService.get_question')
    async def test_stream_followup_cache_hit_records_recent(self, mock_cache_get, mock_add_recent):
        """Cached biblical follow-up with record_recent=True records the question."""
        mock_cache_get.return_value = "Cached follow-up for recent tracking."

        mock_openai = Mock()
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 96
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        request = FollowUpQuestionRequest(
            question="Tell me about Proverbs.",
            user_id=8,
            parent_question_id=900,
            conversation_history=[],
        )

        chunks = [c async for c in service.stream_followup_question(request, record_recent=True)]

        assert chunks[0]["type"] == "cached"
        mock_add_recent.assert_called_once_with(8, "Tell me about Proverbs.")

    @pytest.mark.asyncio
    @patch('app.services.question_service.CacheService.set_question')
    @patch('app.services.question_service.CacheService.get_question', return_value=None)
    async def test_stream_followup_passes_conversation_history_to_openai(self, mock_cache_get, mock_cache_set):
        """Streaming follow-up passes conversation history to OpenAI stream method."""
        call_kwargs = {}

        async def mock_stream(*args, **kwargs):
            call_kwargs.update(kwargs)
            yield {"type": "content", "text": "Answer with context."}

        mock_openai = Mock()
        mock_openai.stream_bible_answer = mock_stream
        mock_openai.is_biblical_answer.return_value = True

        mock_repo = Mock()
        mock_repo.create_question.return_value = 97
        mock_repo.create_answer.return_value = None

        service = QuestionService()
        service.openai_service = mock_openai
        service.question_repo = mock_repo

        history = [
            ConversationMessage(role="user", content="Who was Abraham?"),
            ConversationMessage(role="assistant", content="Abraham was a patriarch."),
        ]

        request = FollowUpQuestionRequest(
            question="Where did he live?",
            user_id=5,
            parent_question_id=950,
            conversation_history=history,
        )

        chunks = [c async for c in service.stream_followup_question(request)]

        expected_history = [
            {"role": "user", "content": "Who was Abraham?"},
            {"role": "assistant", "content": "Abraham was a patriarch."},
        ]
        assert call_kwargs["conversation_history"] == expected_history
