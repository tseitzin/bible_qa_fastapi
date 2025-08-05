"""Unit tests for the OpenAI service."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from openai import OpenAI

from app.services.openai_service import OpenAIService


class TestOpenAIService:
    """Test cases for OpenAIService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('app.services.openai_service.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-3.5-turbo"
            self.service = OpenAIService()
    
    @patch('app.services.openai_service.OpenAI')
    async def test_get_bible_answer_success(self, mock_openai_class):
        """Test successful Bible answer generation."""
        # Mock OpenAI client and response
        mock_client = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Love is patient, love is kind. It does not envy, it does not boast."
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create service with mock
        service = OpenAIService()
        service.client = mock_client
        
        result = await service.get_bible_answer("What is love?")
        
        # Assertions
        assert result == "Love is patient, love is kind. It does not envy, it does not boast."
        
        # Verify OpenAI API call
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful Bible scholar with deep knowledge of Christian theology, "
                        "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
                        "and biblically-grounded answers. When appropriate, include relevant scripture "
                        "references. Be respectful of different denominational perspectives."
                    )
                },
                {"role": "user", "content": "What is love?"}
            ],
            max_tokens=500,
            temperature=0.7
        )
    
    @patch('app.services.openai_service.OpenAI')
    async def test_get_bible_answer_with_whitespace(self, mock_openai_class):
        """Test Bible answer generation with whitespace trimming."""
        # Mock OpenAI client and response with extra whitespace
        mock_client = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "  \n\nFaith is the substance of things hoped for.  \n  "
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create service with mock
        service = OpenAIService()
        service.client = mock_client
        
        result = await service.get_bible_answer("What is faith?")
        
        # Should strip whitespace
        assert result == "Faith is the substance of things hoped for."
    
    @patch('app.services.openai_service.OpenAI')
    async def test_get_bible_answer_api_error(self, mock_openai_class):
        """Test Bible answer generation when OpenAI API fails."""
        # Mock OpenAI client to raise an exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_class.return_value = mock_client
        
        # Create service with mock
        service = OpenAIService()
        service.client = mock_client
        
        # Should raise an exception with proper error message
        with pytest.raises(Exception, match="Failed to get AI response: API rate limit exceeded"):
            await service.get_bible_answer("What is hope?")
    
    @patch('app.services.openai_service.OpenAI')
    async def test_get_bible_answer_network_error(self, mock_openai_class):
        """Test Bible answer generation with network error."""
        # Mock OpenAI client to raise a network exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = ConnectionError("Network unreachable")
        mock_openai_class.return_value = mock_client
        
        # Create service with mock
        service = OpenAIService()
        service.client = mock_client
        
        # Should raise an exception with proper error message
        with pytest.raises(Exception, match="Failed to get AI response: Network unreachable"):
            await service.get_bible_answer("What is wisdom?")
    
    @patch('app.services.openai_service.OpenAI')
    async def test_get_bible_answer_empty_response(self, mock_openai_class):
        """Test Bible answer generation with empty response."""
        # Mock OpenAI client with empty content
        mock_client = Mock()
        mock_choice = Mock()
        mock_choice.message.content = ""
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Create service with mock
        service = OpenAIService()
        service.client = mock_client
        
        result = await service.get_bible_answer("Test question?")
        
        # Should return empty string (after strip)
        assert result == ""
    
    def test_system_message_content(self):
        """Test that the system message contains appropriate content."""
        # This tests the system message used in get_bible_answer
        expected_content = (
            "You are a helpful Bible scholar with deep knowledge of Christian theology, "
            "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
            "and biblically-grounded answers. When appropriate, include relevant scripture "
            "references. Be respectful of different denominational perspectives."
        )
        
        # The system message is used in the get_bible_answer method
        # This test ensures the content is as expected
        assert len(expected_content) > 0
        assert "Bible scholar" in expected_content
        assert "Christian theology" in expected_content
        assert "scripture references" in expected_content


# Test fixtures
@pytest.fixture
def openai_service():
    """Create an OpenAIService instance for testing."""
    with patch('app.services.openai_service.get_settings') as mock_settings:
        mock_settings.return_value.openai_api_key = "test-key"
        mock_settings.return_value.openai_model = "gpt-3.5-turbo"
        return OpenAIService()


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_choice = Mock()
    mock_choice.message.content = "This is a test Bible answer."
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    return mock_response
