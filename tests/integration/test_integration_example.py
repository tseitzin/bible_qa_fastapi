"""Integration tests for Bible Q&A FastAPI application."""
import pytest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from app.main import app
from app.database import QuestionRepository
from app.config import get_settings

# Mark integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_db():
    """Set up test database environment."""
    # Load test environment variables
    test_env_path = "/Users/tim/Projects/bible_qa_fastapi/.env.test"
    if os.path.exists(test_env_path):
        from dotenv import load_dotenv
        load_dotenv(test_env_path, override=True)
    
    settings = get_settings()
    yield settings.db_name
    
    # Note: Database cleanup is handled by the setup script


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_openai_service():
    """Mock OpenAI service for integration tests."""
    with patch('app.services.openai_service.OpenAIService.get_bible_answer') as mock_method:
        mock_method.return_value = "Mocked Bible answer for integration testing."
        yield mock_method


class TestDatabaseIntegration:
    """Integration tests with real database."""
    @staticmethod
    def _ensure_user(user_id: int):
        """Create a user row if not exists (minimal schema)."""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        settings = get_settings()
        conn = psycopg2.connect(cursor_factory=RealDictCursor, **settings.db_config)
        try:
            with conn, conn.cursor() as cur:
                cur.execute("INSERT INTO users (id, username) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING;", (user_id, f"user_{user_id}"))
        finally:
            conn.close()
    
    def test_question_repository_create_and_retrieve(self, test_db):
        """Test QuestionRepository with real PostgreSQL database."""
        self._ensure_user(123)
        # Create a question
        question_id = QuestionRepository.create_question(
            user_id=123,
            question="What does John 3:16 mean?"
        )
        
        assert question_id is not None
        assert isinstance(question_id, int)
        
        # Create an answer
        QuestionRepository.create_answer(
            question_id=question_id,
            answer="John 3:16 speaks of God's love for the world..."
        )
        
        # Retrieve history
        history = QuestionRepository.get_question_history(user_id=123, limit=10)
        
        assert len(history) >= 1
        
        # Find our question
        our_question = next((q for q in history if q["id"] == question_id), None)
        assert our_question is not None
        assert our_question["question"] == "What does John 3:16 mean?"
        assert "John 3:16" in our_question["answer"]
    
    def test_multiple_users_isolation(self, test_db):
        """Test that different users' data is properly isolated."""
        self._ensure_user(100)
        self._ensure_user(200)
        # Create questions for different users
        q1_id = QuestionRepository.create_question(user_id=100, question="User 100 question")
        q2_id = QuestionRepository.create_question(user_id=200, question="User 200 question")
        
        QuestionRepository.create_answer(q1_id, "Answer for user 100")
        QuestionRepository.create_answer(q2_id, "Answer for user 200")
        
        # Check user 100's history
        history_100 = QuestionRepository.get_question_history(user_id=100, limit=10)
        user_100_questions = [q["question"] for q in history_100]
        assert "User 100 question" in user_100_questions
        assert "User 200 question" not in user_100_questions
        
        # Check user 200's history
        history_200 = QuestionRepository.get_question_history(user_id=200, limit=10)
        user_200_questions = [q["question"] for q in history_200]
        assert "User 200 question" in user_200_questions
        assert "User 100 question" not in user_200_questions
    
    def test_pagination_limits(self, test_db):
        """Test that pagination works correctly."""
        user_id = 999
        self._ensure_user(user_id)
        
        # Create multiple questions
        question_ids = []
        for i in range(5):
            q_id = QuestionRepository.create_question(
                user_id=user_id,
                question=f"Test question {i}"
            )
            QuestionRepository.create_answer(q_id, f"Test answer {i}")
            question_ids.append(q_id)
        
        # Test limit functionality
        history_limited = QuestionRepository.get_question_history(user_id=user_id, limit=3)
        assert len(history_limited) == 3
        
        # Should get most recent questions first (assuming ORDER BY created_at DESC)
        history_all = QuestionRepository.get_question_history(user_id=user_id, limit=10)
        assert len(history_all) >= 5


class TestAPIIntegration:
    """Integration tests for API endpoints with real database."""
    
    def test_ask_question_end_to_end(self, test_db, client, mock_openai_service):
        """Test complete question flow with real database and mocked OpenAI."""
        # Configure the mock to return a specific answer
        mock_openai_service.return_value = "This verse demonstrates God's incredible love for humanity."
        
        # Submit question via API
        # Ensure user exists for FK
        TestDatabaseIntegration._ensure_user(456)
        response = client.post("/api/ask", json={
            "question": "What is the significance of John 3:16?",
            "user_id": 456
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "question_id" in data
        assert "God's incredible love" in data["answer"]
        
        question_id = data["question_id"]
        
        # Verify question was stored in database via API
        history_response = client.get("/api/history/456")
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        assert history_data["total"] >= 1
        
        # Find our question in the history
        our_question = next(
            (q for q in history_data["questions"] 
             if q["id"] == question_id), 
            None
        )
        assert our_question is not None
        assert our_question["question"] == "What is the significance of John 3:16?"
        assert "God's incredible love" in our_question["answer"]
    
    def test_health_check_endpoint(self, test_db, client):
        """Test that health check works with database connection."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
    
    def test_history_endpoint_pagination(self, test_db, client, mock_openai_service):
        """Test history endpoint with real database pagination."""
        user_id = 789
        TestDatabaseIntegration._ensure_user(user_id)
        
        # Configure the mock
        mock_openai_service.return_value = "Test answer"
        
        # Create some test data via API
        for i in range(3):
            response = client.post("/api/ask", json={
                "question": f"Test question {i}",
                "user_id": user_id
            })
            assert response.status_code == 200
        
        # Test different limits
        response_limit_2 = client.get(f"/api/history/{user_id}?limit=2")
        assert response_limit_2.status_code == 200
        data_limit_2 = response_limit_2.json()
        assert len(data_limit_2["questions"]) == 2
        
        response_limit_5 = client.get(f"/api/history/{user_id}?limit=5")
        assert response_limit_5.status_code == 200
        data_limit_5 = response_limit_5.json()
        assert len(data_limit_5["questions"]) >= 3
    
    def test_error_handling_with_real_db(self, test_db, client, mock_openai_service):
        """Test error handling when OpenAI fails but database is real."""
        # Configure mock to raise an exception
        mock_openai_service.side_effect = Exception("OpenAI API Error")
        
        TestDatabaseIntegration._ensure_user(999)
        response = client.post("/api/ask", json={
            "question": "This will fail",
            "user_id": 999
        })
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        
        # Verify no question was stored in database when OpenAI fails
        history_response = client.get("/api/history/999")
        assert history_response.status_code == 200
        history_data = history_response.json()
        
        # Should not find the failed question
        failed_questions = [q for q in history_data["questions"] if q["question"] == "This will fail"]
        assert len(failed_questions) == 0
