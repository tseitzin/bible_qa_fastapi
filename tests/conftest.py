"""Configuration for pytest."""
import sys
import os

# Add the app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# Common test fixtures can be defined here
import pytest
from unittest.mock import Mock


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
    settings.allowed_origins = ["http://localhost:3000"]
    return settings
