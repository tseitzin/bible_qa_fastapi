"""Unit tests for the OpenAI service."""
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.services.openai_service import OpenAIService, SYSTEM_PROMPT, NON_BIBLICAL_RESPONSE
from app.utils.exceptions import OpenAIError


class TestGetBibleAnswer:
    """Test cases for get_bible_answer method."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()
    @pytest.mark.asyncio
    async def test_timeout_recovers_with_trimmed_history(self, monkeypatch):
        """Service retries with smaller history windows before surfacing timeout."""

        attempt_messages = []

        async def fake_request(messages, max_tokens):
            attempt_messages.append(messages)
            if len(attempt_messages) < 3:
                raise asyncio.TimeoutError()
            response = Mock()
            response.output_text = "Recovered"
            response.status = "completed"
            return response

        self.service._request_response = fake_request

        history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]

        answer = await self.service.get_bible_answer("Follow up?", conversation_history=history)

        assert answer == "Recovered"
        assert len(attempt_messages) == 3
        assert len(attempt_messages[0]) == len(history) + 2
        assert len(attempt_messages[-1]) == 2

    @pytest.mark.asyncio
    async def test_returns_correctly_formatted_response(self):
        """Test that get_bible_answer returns a correctly formatted AI response."""
        # Mock the OpenAI response
        mock_response = Mock()
        mock_response.output_text = "Love is patient, love is kind (1 Corinthians 13:4)."
        mock_response.status = "complete"

        async def mock_request(*args, **kwargs):
            return mock_response

        self.service._request_response = mock_request

        result = await self.service.get_bible_answer("What does the Bible say about love?")

        assert result == "Love is patient, love is kind (1 Corinthians 13:4)."
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_incorporates_conversation_history(self):
        """Test that get_bible_answer correctly incorporates conversation history into the prompt."""
        conversation_history = [
            {"role": "user", "content": "Who is Jesus?"},
            {"role": "assistant", "content": "Jesus is the Son of God and central figure of Christianity."},
        ]

        mock_response = Mock()
        mock_response.output_text = "His ministry began around age 30."
        mock_response.status = "complete"

        messages_passed = None

        async def mock_request(messages, max_tokens):
            nonlocal messages_passed
            messages_passed = messages
            return mock_response

        self.service._request_response = mock_request

        result = await self.service.get_bible_answer(
            "When did he begin his ministry?",
            conversation_history=conversation_history
        )

        # Verify the result
        assert result == "His ministry began around age 30."

        # Verify the messages include system prompt, history, and new question
        assert len(messages_passed) == 4  # system + 2 history + 1 new question
        assert messages_passed[0]["role"] == "system"
        assert messages_passed[0]["content"][0]["text"] == SYSTEM_PROMPT
        assert messages_passed[1]["role"] == "user"
        assert messages_passed[1]["content"][0]["text"] == "Who is Jesus?"
        assert messages_passed[2]["role"] == "assistant"
        assert messages_passed[2]["content"][0]["text"] == "Jesus is the Son of God and central figure of Christianity."
        assert messages_passed[3]["role"] == "user"
        assert messages_passed[3]["content"][0]["text"] == "When did he begin his ministry?"

    @pytest.mark.asyncio
    async def test_limits_conversation_history_to_max(self):
        """Conversation history is trimmed to the configured maximum length."""
        self.service.max_history_messages = 1
        conversation_history = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "Third"},
        ]

        mock_response = Mock()
        mock_response.output_text = "Answer"
        mock_response.status = "complete"

        captured_messages = None

        async def mock_request(messages, max_tokens):
            nonlocal captured_messages
            captured_messages = messages
            return mock_response

        self.service._request_response = mock_request

        await self.service.get_bible_answer("Trim history?", conversation_history=conversation_history)

        assert captured_messages is not None
        # Expect system + last history entry + user question
        assert len(captured_messages) == 3
        assert captured_messages[1]["content"][0]["text"] == "Third"

    @pytest.mark.asyncio
    async def test_handles_asyncio_timeout(self):
        """asyncio.TimeoutError is converted into an OpenAIError."""

        async def mock_request(*args, **kwargs):
            raise asyncio.TimeoutError()

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("Trigger timeout")

        assert "timed out" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_is_biblical_answer_detection(self):
        """Helper identifies refusals as non-biblical."""

        mock_response = Mock()
        mock_response.output_text = NON_BIBLICAL_RESPONSE
        mock_response.status = "complete"

        async def mock_request(*args, **kwargs):
            return mock_response

        self.service._request_response = mock_request

        answer = await self.service.get_bible_answer("Tell me about movies")

        assert answer == NON_BIBLICAL_RESPONSE
        assert not self.service.is_biblical_answer(answer)

    @pytest.mark.asyncio
    async def test_retries_with_increased_tokens_on_truncation(self):
        """Test that get_bible_answer retries with increased max_output_tokens if truncated."""
        # First response: truncated
        mock_response_truncated = Mock()
        mock_response_truncated.output_text = "This is a truncated response"
        mock_response_truncated.status = "incomplete"
        mock_response_truncated.incomplete_details = Mock()
        mock_response_truncated.incomplete_details.reason = "max_output_tokens"

        # Second response: complete
        mock_response_complete = Mock()
        mock_response_complete.output_text = "This is the complete response with more details."
        mock_response_complete.status = "complete"

        call_count = 0
        tokens_used = []

        async def mock_request(messages, max_tokens):
            nonlocal call_count
            tokens_used.append(max_tokens)
            call_count += 1
            if call_count == 1:
                return mock_response_truncated
            return mock_response_complete

        self.service._request_response = mock_request

        result = await self.service.get_bible_answer("Tell me about the Gospel of John.")

        # Verify retry occurred
        assert call_count == 2
        assert tokens_used[0] == 900  # Initial max_output_tokens
        assert tokens_used[1] == 1500  # Retry with higher max_output_tokens
        assert result == "This is the complete response with more details."

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_bad_request(self):
        """Test that get_bible_answer raises OpenAIError on BadRequestError."""
        async def mock_request(*args, **kwargs):
            raise BadRequestError("Invalid request", response=Mock(), body=None)

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is faith?")

        assert exc_info.value.status_code == 503
        assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_rate_limit(self):
        """Test that get_bible_answer raises OpenAIError on RateLimitError."""
        async def mock_request(*args, **kwargs):
            raise RateLimitError("Rate limit exceeded", response=Mock(), body=None)

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is hope?")

        assert exc_info.value.status_code == 503
        assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_timeout(self):
        """Test that get_bible_answer raises OpenAIError on APITimeoutError."""
        async def mock_request(*args, **kwargs):
            raise APITimeoutError("Request timeout")

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is wisdom?")

        assert exc_info.value.status_code == 503
        assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_connection_error(self):
        """Test that get_bible_answer raises OpenAIError on APIConnectionError."""
        async def mock_request(*args, **kwargs):
            raise APIConnectionError("Connection failed")

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is grace?")

        assert exc_info.value.status_code == 503
        assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_api_error(self):
        """Test that get_bible_answer raises OpenAIError on generic APIError."""
        async def mock_request(*args, **kwargs):
            raise APIError("API error occurred", request=Mock(), body=None)

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is salvation?")

        assert exc_info.value.status_code == 503
        assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_openai_error_on_empty_response(self):
        """Test that get_bible_answer raises OpenAIError when response is empty."""
        mock_response = Mock()
        mock_response.output_text = "   "  # Whitespace only
        mock_response.status = "complete"

        async def mock_request(*args, **kwargs):
            return mock_response

        self.service._request_response = mock_request

        with pytest.raises(OpenAIError) as exc_info:
            await self.service.get_bible_answer("What is truth?")

        assert exc_info.value.status_code == 503
        assert "AI service returned an empty response" in exc_info.value.detail


class TestExtractText:
    """Test cases for _extract_text method."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()

    def test_extract_text_from_output_text_attribute(self):
        """Test _extract_text extracts from output_text attribute."""
        mock_response = Mock()
        mock_response.output_text = "  This is the response text.  "

        result = self.service._extract_text(mock_response)

        assert result == "This is the response text."

    def test_extract_text_from_output_list(self):
        """Test _extract_text extracts from output list with content."""
        mock_response = Mock()
        mock_response.output_text = None
        mock_response.output = [
            Mock(content=[
                Mock(text="First segment"),
                Mock(text="Second segment"),
            ])
        ]

        result = self.service._extract_text(mock_response)

        assert result == "First segment\n\nSecond segment"


class TestNormalizeHistory:
    """Tests for history normalization helpers."""

    def setup_method(self):
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()

    def test_normalize_history_casts_non_string_content(self):
        """Non-string history content is coerced to a string representation."""
        history = [{"role": "assistant", "content": {"key": "value"}}]
        normalized = self.service._normalize_history(history)
        assert normalized[0]["content"][0]["text"] == "{'key': 'value'}"

    def test_normalize_history_supports_objects(self):
        """History entries provided as objects (e.g., Pydantic models) are supported."""

        class Msg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        history = [Msg("assistant", "Typed message")]
        normalized = self.service._normalize_history(history)
        assert normalized[0]["role"] == "assistant"
        assert normalized[0]["content"][0]["text"] == "Typed message"


class TestRequestResponse:
    """Tests for the _request_response helper."""

    def setup_method(self):
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()

    @pytest.mark.asyncio
    async def test_request_response_uses_wait_for_with_timeout(self):
        """When a timeout is configured, asyncio.wait_for wraps the request task."""

        async def fake_to_thread(*args, **kwargs):
            return "ok"

        with patch('app.services.openai_service.asyncio.to_thread', side_effect=fake_to_thread) as mock_to_thread:
            with patch('app.services.openai_service.asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                mock_wait_for.return_value = "wrapped"

                result = await self.service._request_response([], 100)

                mock_to_thread.assert_called_once()
                mock_wait_for.assert_awaited_once()
                assert result == "wrapped"

    @pytest.mark.asyncio
    async def test_request_response_returns_directly_without_timeout(self):
        """When no timeout is set, the task result is awaited directly without wait_for."""

        self.service.request_timeout = 0

        async def fake_to_thread(*args, **kwargs):
            return "direct"

        with patch('app.services.openai_service.asyncio.to_thread', side_effect=fake_to_thread) as mock_to_thread:
            with patch('app.services.openai_service.asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                result = await self.service._request_response([], 50)

                mock_to_thread.assert_called_once()
                mock_wait_for.assert_not_awaited()
                assert result == "direct"


class TestSafeGet:
    """Tests for the _safe_get helper."""

    def setup_method(self):
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()

    def test_safe_get_returns_none_when_no_accessors_available(self):
        """Objects without attribute, mapping, or model_dump accessors return None."""

        class Opaque:
            pass

        assert self.service._safe_get(Opaque(), "field") is None

    def test_extract_text_from_output_with_output_text_field(self):
        """Test _extract_text extracts from output_text field in content."""
        mock_response = Mock()
        mock_response.output_text = None
        mock_response.output = [
            Mock(content=[
                Mock(text=None, output_text="Response with output_text field"),
            ])
        ]

        result = self.service._extract_text(mock_response)

        assert result == "Response with output_text field"

    def test_extract_text_from_dict_response(self):
        """Test _extract_text extracts from dict-like response."""
        mock_response = {
            "output": [
                {
                    "content": [
                        {"text": "Dictionary response"},
                    ]
                }
            ]
        }

        result = self.service._extract_text(mock_response)

        assert result == "Dictionary response"

    def test_extract_text_with_model_dump(self):
        """Test _extract_text extracts from response with model_dump method."""
        # Create a custom class that only has model_dump method
        class ResponseWithModelDump:
            def model_dump(self):
                return {
                    "output": [
                        {
                            "content": [
                                {"text": "Model dump response"},
                            ]
                        }
                    ]
                }

        mock_response = ResponseWithModelDump()

        result = self.service._extract_text(mock_response)

        assert result == "Model dump response"

    def test_extract_text_multiple_output_items(self):
        """Test _extract_text handles multiple output items with multiple content parts."""
        mock_response = Mock()
        mock_response.output_text = None
        mock_response.output = [
            Mock(content=[
                Mock(text="Part 1"),
                Mock(text="Part 2"),
            ]),
            Mock(content=[
                Mock(text="Part 3"),
            ])
        ]

        result = self.service._extract_text(mock_response)

        assert result == "Part 1\n\nPart 2\n\nPart 3"

    def test_extract_text_returns_empty_for_none(self):
        """Test _extract_text returns empty string for None response."""
        result = self.service._extract_text(None)

        assert result == ""

    def test_extract_text_returns_empty_for_no_content(self):
        """Test _extract_text returns empty string when no text content found."""
        mock_response = Mock()
        mock_response.output_text = None
        mock_response.output = []

        result = self.service._extract_text(mock_response)

        assert result == ""

    def test_extract_text_strips_whitespace_from_segments(self):
        """Test _extract_text strips whitespace from individual segments."""
        mock_response = Mock()
        mock_response.output_text = None
        mock_response.output = [
            Mock(content=[
                Mock(text="  First segment  "),
                Mock(text="\n\nSecond segment\n\n"),
            ])
        ]

        result = self.service._extract_text(mock_response)

        assert result == "First segment\n\nSecond segment"


class TestIsBiblicalAnswer:
    """Unit tests for biblical response detection helper."""

    def setup_method(self):
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = "test-api-key"
            mock_settings.return_value.openai_model = "gpt-5-mini"
            mock_settings.return_value.openai_max_output_tokens = 900
            mock_settings.return_value.openai_max_output_tokens_retry = 1500
            mock_settings.return_value.openai_retry_on_truncation = True
            mock_settings.return_value.openai_reasoning_effort = "low"
            mock_settings.return_value.openai_request_timeout = 30
            mock_settings.return_value.openai_max_history_messages = 12
            self.service = OpenAIService()

    def test_returns_true_for_biblical_answer(self):
        assert self.service.is_biblical_answer("Jesus wept.") is True

    def test_returns_false_for_refusal(self):
        assert self.service.is_biblical_answer(NON_BIBLICAL_RESPONSE) is False

    def test_returns_false_for_blank_answer(self):
        assert self.service.is_biblical_answer("  ") is False

    def test_returns_false_when_refusal_embedded(self):
        wrapped = f">>> {NON_BIBLICAL_RESPONSE} <<<"
        assert self.service.is_biblical_answer(wrapped) is False
