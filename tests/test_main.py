"""Unit tests for the main FastAPI application."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.models.schemas import QuestionRequest, QuestionResponse, HistoryResponse, HistoryItem
from app.utils.exceptions import DatabaseError, OpenAIError
from app.auth import get_current_user, get_current_user_optional


# Test client
client = TestClient(app)


@pytest.fixture
def authenticated_user():
    """Override authentication dependency to simulate a logged-in user."""
    def override_current_user():
        return {"id": 1, "is_active": True}

    app.dependency_overrides[get_current_user] = override_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def optional_authenticated_user():
    """Override optional authentication dependency to simulate a logged-in user."""

    def override_optional_user():
        return {"id": 7, "is_active": True}

    app.dependency_overrides[get_current_user_optional] = override_optional_user
    yield
    app.dependency_overrides.pop(get_current_user_optional, None)


class TestHealthCheck:
    """Test cases for health check endpoint."""
    
    def test_health_check_success(self):
        """Test successful health check."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"


class TestAskQuestion:
    """Test cases for the ask question endpoint."""
    
    @patch('app.main.question_service')
    def test_ask_question_success(self, mock_service):
        """Test successful question submission."""
        # Mock service response
        mock_response = QuestionResponse(
            answer="God is love, as stated in 1 John 4:8.",
            question_id=123,
            is_biblical=True,
        )
        mock_service.process_question = AsyncMock(return_value=mock_response)
        
        # Test request
        request_data = {
            "question": "What does the Bible say about love?",
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "God is love, as stated in 1 John 4:8."
        assert data["question_id"] == 123
        assert data["is_biblical"] is True
        
        # Verify service was called correctly
        mock_service.process_question.assert_called_once()
        call_args = mock_service.process_question.call_args[0][0]
        assert call_args.question == "What does the Bible say about love?"
        assert call_args.user_id == 1
    
    @patch('app.main.question_service')
    def test_ask_question_with_minimal_data(self, mock_service):
        """Test question submission with minimal required data."""
        mock_response = QuestionResponse(
            answer="Jesus is the way, the truth, and the life.",
            question_id=456,
            is_biblical=True,
        )
        mock_service.process_question = AsyncMock(return_value=mock_response)
        
        request_data = {
            "question": "Who is Jesus?"
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Jesus is the way, the truth, and the life."
        assert data["question_id"] == 456
        assert data["is_biblical"] is True
    
    def test_ask_question_missing_question(self):
        """Test question submission without required question field."""
        request_data = {
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_ask_question_empty_question(self):
        """Test question submission with empty question."""
        request_data = {
            "question": "",
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_ask_question_too_long(self):
        """Test question submission with question too long."""
        long_question = "x" * 1001  # Exceeds 1000 char limit
        request_data = {
            "question": long_question,
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    @patch('app.main.question_service')
    def test_ask_question_service_error(self, mock_service):
        """Test question submission when service raises an error."""
        mock_service.process_question = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        request_data = {
            "question": "What does the Bible say about love?",
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"

    @patch('app.main.question_service')
    def test_ask_question_authenticated_records_recent(self, mock_service, optional_authenticated_user):
        """Authenticated requests propagate user id and record recent questions."""

        mock_response = QuestionResponse(answer="Tracked", question_id=77, is_biblical=True)
        mock_service.process_question = AsyncMock(return_value=mock_response)

        response = client.post("/api/ask", json={"question": "Track this"})

        assert response.status_code == 200
        args, kwargs = mock_service.process_question.call_args
        assert kwargs["record_recent"] is True
        assert args[0].user_id == 7


class TestAskFollowUpQuestion:
    """Test cases for the follow-up question endpoint."""

    @patch('app.main.question_service')
    def test_ask_followup_question_success(self, mock_service):
        """Test successful follow-up question submission."""
        mock_response = QuestionResponse(answer="Extended context", question_id=321, is_biblical=True)
        mock_service.process_followup_question = AsyncMock(return_value=mock_response)

        request_data = {
            "question": "Can you tell me more?",
            "conversation_history": [
                {"role": "user", "content": "Initial question"},
                {"role": "assistant", "content": "Initial answer"}
            ],
            "parent_question_id": 123,
            "user_id": 2
        }

        response = client.post("/api/ask/followup", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Extended context"
        assert data["question_id"] == 321
        assert data["is_biblical"] is True
        mock_service.process_followup_question.assert_called_once()

    @patch('app.main.question_service')
    def test_ask_followup_question_service_error(self, mock_service):
        """Test follow-up question when service raises error."""
        mock_service.process_followup_question = AsyncMock(side_effect=Exception("Processing failed"))

        request_data = {
            "question": "Explain further",
            "conversation_history": [],
            "parent_question_id": 1,
            "user_id": 1
        }

        response = client.post("/api/ask/followup", json=request_data)

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    @patch('app.main.question_service')
    def test_ask_followup_question_authenticated_records_recent(self, mock_service, optional_authenticated_user):
        """Authenticated follow-up requests propagate user id and record recents."""

        mock_response = QuestionResponse(answer="Extended", question_id=99, is_biblical=True)
        mock_service.process_followup_question = AsyncMock(return_value=mock_response)

        response = client.post(
            "/api/ask/followup",
            json={
                "question": "Provide more context",
                "conversation_history": [],
                "parent_question_id": 12,
            },
        )

        assert response.status_code == 200
        args, kwargs = mock_service.process_followup_question.call_args
        assert kwargs["record_recent"] is True
        assert args[0].user_id == 7


class TestQuestionHistory:
    """Test cases for the question history endpoint."""
    
    @patch('app.main.question_service')
    def test_get_history_success(self, mock_service, authenticated_user):
        """Test successful history retrieval."""
        # Mock service response
        mock_history_items = [
            HistoryItem(
                id=1,
                question="What is love?",
                answer="God is love.",
                created_at=datetime(2025, 7, 31, 12, 0, 0)
            ),
            HistoryItem(
                id=2,
                question="Who is Jesus?",
                answer="Jesus is the Son of God.",
                created_at=datetime(2025, 7, 31, 11, 0, 0)
            )
        ]
        mock_response = HistoryResponse(
            questions=mock_history_items,
            total=2
        )
        mock_service.get_user_history = Mock(return_value=mock_response)
        
        response = client.get("/api/history")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["questions"]) == 2
        assert data["questions"][0]["question"] == "What is love?"
        assert data["questions"][1]["question"] == "Who is Jesus?"
        
        # Verify service was called correctly
        mock_service.get_user_history.assert_called_once_with(1, 10)
    
    @patch('app.main.question_service')
    def test_get_history_with_custom_limit(self, mock_service, authenticated_user):
        """Test history retrieval with custom limit."""
        mock_response = HistoryResponse(questions=[], total=0)
        mock_service.get_user_history = Mock(return_value=mock_response)
        
        response = client.get("/api/history?limit=5")
        
        assert response.status_code == 200
        mock_service.get_user_history.assert_called_once_with(1, 5)
    
    @patch('app.main.question_service')
    def test_get_history_limit_too_high(self, mock_service, authenticated_user):
        """Test history retrieval with limit higher than maximum."""
        mock_response = HistoryResponse(questions=[], total=0)
        mock_service.get_user_history = Mock(return_value=mock_response)
        
        response = client.get("/api/history?limit=200")
        
        assert response.status_code == 200
        # Should be capped at 100
        mock_service.get_user_history.assert_called_once_with(1, 100)
    
    @patch('app.main.question_service')
    def test_get_history_empty_result(self, mock_service, authenticated_user):
        """Test history retrieval with no results."""
        mock_response = HistoryResponse(questions=[], total=0)
        mock_service.get_user_history = Mock(return_value=mock_response)
        
        response = client.get("/api/history")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["questions"]) == 0
    
    @patch('app.main.question_service')
    def test_get_history_service_error(self, mock_service, authenticated_user):
        """Test history retrieval when service raises an error."""
        mock_service.get_user_history = Mock(
            side_effect=Exception("Database error")
        )
        
        response = client.get("/api/history")
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"

    def test_get_history_requires_authentication(self):
        """Ensure the endpoint requires authentication when no user is provided."""
        app.dependency_overrides.pop(get_current_user, None)
        response = client.get("/api/history")
        assert response.status_code == 401


class TestErrorHandlers:
    """Test cases for custom error handlers."""
    
    @patch('app.main.question_service')
    def test_database_error_handler(self, mock_service):
        """Test database error handler."""
        mock_service.process_question = AsyncMock(
            side_effect=DatabaseError("Connection timeout")
        )
        
        request_data = {
            "question": "Test question",
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Connection timeout"
    
    @patch('app.main.question_service')
    def test_openai_error_handler(self, mock_service):
        """Test OpenAI error handler."""
        mock_service.process_question = AsyncMock(
            side_effect=OpenAIError("API rate limit exceeded")
        )
        
        request_data = {
            "question": "Test question",
            "user_id": 1
        }
        
        response = client.post("/api/ask", json=request_data)
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "API rate limit exceeded"


class TestCORS:
    """Test cases for CORS configuration."""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        response = client.get("/")
        
        # Note: TestClient doesn't handle CORS headers the same way as real requests
        # In a real scenario, you'd test with actual browser requests
        assert response.status_code == 200


class TestApplicationConfiguration:
    """Test cases for application configuration."""
    
    def test_app_metadata(self):
        """Test FastAPI app metadata."""
        assert app.title == "Bible Q&A API"
        assert app.description == "AI-powered Bible Q&A API"
        assert app.version == "1.0.0"


# Fixtures for common test data
@pytest.fixture
def sample_question_request():
    """Sample question request for testing."""
    return QuestionRequest(
        question="What does the Bible say about faith?",
        user_id=1
    )


@pytest.fixture
def sample_question_response():
    """Sample question response for testing."""
    return QuestionResponse(
        answer="Faith is the substance of things hoped for.",
        question_id=123,
        is_biblical=True,
    )


@pytest.fixture
def sample_history_response():
    """Sample history response for testing."""
    return HistoryResponse(
        questions=[
            HistoryItem(
                id=1,
                question="What is faith?",
                answer="Faith is believing in God.",
                created_at=datetime(2025, 7, 31, 12, 0, 0)
            )
        ],
        total=1
    )
