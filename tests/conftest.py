"""Shared test fixtures for the Bible Q&A API."""
import sys
import os

# Add the app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings():
    """Mock application settings for testing."""
    settings = Mock()
    settings.app_name = "Test Bible Q&A API"
    settings.debug = True
    settings.db_name = "test_db"
    settings.db_user = "test_user"
    settings.db_password = "test_password"
    settings.db_host = "localhost"
    settings.db_port = 5432
    settings.openai_api_key = "test-openai-key"
    settings.openai_model = "gpt-3.5-turbo"
    settings.openai_max_output_tokens = 1500
    settings.openai_max_output_tokens_retry = 1200
    settings.openai_retry_on_truncation = True
    settings.openai_reasoning_effort = "low"
    settings.openai_request_timeout = 45
    settings.openai_max_history_messages = 10
    settings.allowed_origins = ["http://localhost:3000"]
    settings.secret_key = "test-secret-key"
    settings.auth_cookie_name = "bible_qa_auth"
    settings.auth_cookie_domain = ""
    settings.auth_cookie_secure = False
    settings.auth_cookie_samesite = "lax"
    settings.auth_cookie_max_age = 604800
    settings.csrf_cookie_name = "bible_qa_csrf"
    settings.csrf_cookie_secure = False
    settings.csrf_cookie_samesite = "strict"
    settings.csrf_cookie_max_age = 21600
    settings.csrf_header_name = "X-CSRF-Token"
    settings.csrf_protection_enabled = False
    settings.csrf_exempt_paths = []
    settings.redis_url = "redis://localhost:6379/0"
    settings.cache_enabled = False
    settings.mcp_api_key = ""
    return settings


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Standard authenticated user fixture."""
    return {
        "id": 1,
        "email": "test@example.com",
        "username": "testuser",
        "is_active": True,
        "is_admin": False,
        "is_guest": False,
    }


@pytest.fixture
def mock_admin_user():
    """Admin user fixture."""
    return {
        "id": 1,
        "email": "admin@example.com",
        "username": "admin",
        "is_active": True,
        "is_admin": True,
        "is_guest": False,
    }


@pytest.fixture
def mock_guest_user():
    """Guest user fixture."""
    return {
        "id": 99,
        "email": "guest_abc123@guest.local",
        "username": "guest_abc123",
        "is_active": True,
        "is_admin": False,
        "is_guest": True,
    }


@pytest.fixture
def authenticated_client(test_client, mock_user):
    """Test client with authenticated user dependency overrides."""
    from app.main import app
    from app.auth import get_current_user_dependency, get_current_user_optional_dependency

    async def override_get_current_user(request=None):
        return mock_user

    app.dependency_overrides[get_current_user_dependency] = override_get_current_user
    app.dependency_overrides[get_current_user_optional_dependency] = override_get_current_user
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(test_client, mock_admin_user):
    """Test client with admin user dependency overrides."""
    from app.main import app
    from app.auth import get_current_user_dependency, get_current_admin_user

    async def override_get_admin():
        return mock_admin_user

    app.dependency_overrides[get_current_user_dependency] = override_get_admin
    app.dependency_overrides[get_current_admin_user] = override_get_admin
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_connection():
    """Mock database connection context manager."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    with patch('app.database.get_db_connection') as mock_get_conn:
        mock_get_conn.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)
        yield mock_conn, mock_cursor


@pytest.fixture
def mock_question_repo():
    """Mock QuestionRepository for service testing."""
    repo = Mock()
    repo.create_question.return_value = 1
    repo.create_answer.return_value = None
    repo.get_question_history.return_value = []
    return repo


@pytest.fixture
def mock_openai_service():
    """Mock OpenAIService for service testing."""
    service = Mock()
    service.is_biblical_answer.return_value = True
    return service
