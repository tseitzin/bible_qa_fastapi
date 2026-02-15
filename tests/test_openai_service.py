"""Unit tests for the OpenAI service."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    RateLimitError,
)

from app.services.openai_service import OpenAIService, NON_BIBLICAL_RESPONSE, SYSTEM_PROMPT
from app.utils.exceptions import OpenAIError


# ---------------------------------------------------------------------------
# Helpers for constructing OpenAI SDK exception objects
# ---------------------------------------------------------------------------

def _make_httpx_response(status_code: int = 400) -> httpx.Response:
    """Create a minimal httpx.Response for OpenAI exception constructors."""
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx.Response(status_code=status_code, request=request)


def _make_httpx_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _make_bad_request_error(msg: str = "Invalid request") -> BadRequestError:
    return BadRequestError(msg, response=_make_httpx_response(400), body=None)


def _make_rate_limit_error(msg: str = "Rate limit exceeded") -> RateLimitError:
    return RateLimitError(msg, response=_make_httpx_response(429), body=None)


def _make_timeout_error() -> APITimeoutError:
    return APITimeoutError(request=_make_httpx_request())


def _make_connection_error(msg: str = "Connection failed") -> APIConnectionError:
    return APIConnectionError(message=msg, request=_make_httpx_request())


def _make_api_error(msg: str = "API error") -> APIError:
    return APIError(msg, request=_make_httpx_request(), body=None)


# ---------------------------------------------------------------------------
# Helpers for constructing mock OpenAI chat completion responses
# ---------------------------------------------------------------------------

def _make_usage(prompt_tokens: int = 50, completion_tokens: int = 100, total_tokens: int = 150):
    """Build a mock usage object."""
    usage = Mock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens
    return usage


def _make_message(content: str = "Test answer", tool_calls=None):
    """Build a mock message object."""
    message = Mock()
    message.content = content
    message.tool_calls = tool_calls
    message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in (tool_calls or [])
        ] or None,
    }
    return message


def _make_choice(message=None, finish_reason: str = "stop"):
    """Build a mock choice object."""
    choice = Mock()
    choice.message = message or _make_message()
    choice.finish_reason = finish_reason
    return choice


def _make_completion(content: str = "Test answer", finish_reason: str = "stop",
                     tool_calls=None, usage=None):
    """Build a full mock chat completion response."""
    message = _make_message(content=content, tool_calls=tool_calls)
    choice = _make_choice(message=message, finish_reason=finish_reason)
    response = Mock()
    response.choices = [choice]
    response.usage = usage or _make_usage()
    return response


def _make_tool_call(call_id: str = "call_1", name: str = "get_verse",
                    arguments: str = '{"book": "John", "chapter": 3, "verse": 16}'):
    """Build a mock tool call object."""
    tc = Mock()
    tc.id = call_id
    tc.function = Mock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def _make_stream_chunk(content: str = None, finish_reason: str = None, usage=None):
    """Build a mock streaming chunk."""
    chunk = Mock()
    delta = Mock()
    delta.content = content
    choice = Mock()
    choice.delta = delta
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


# ---------------------------------------------------------------------------
# Shared fixture to create an OpenAIService with mocked settings
# ---------------------------------------------------------------------------

@pytest.fixture
def openai_service():
    """Create an OpenAIService with mocked settings and mocked client."""
    with patch("app.config.get_settings") as mock_get_settings:
        settings = mock_get_settings.return_value
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-test"
        settings.openai_max_output_tokens = 100
        settings.openai_request_timeout = 30
        settings.openai_max_history_messages = 10
        service = OpenAIService()
    # Replace the real OpenAI client with a Mock
    service.client = Mock()
    return service


# ===================================================================
# TestIsBiblicalAnswer - kept intact from original
# ===================================================================

class TestIsBiblicalAnswer:
    """Unit tests for biblical response detection helper."""

    def setup_method(self):
        with patch("app.config.get_settings") as mock_settings:
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

    def test_returns_false_for_none(self):
        assert self.service.is_biblical_answer(None) is False

    def test_returns_false_for_empty_string(self):
        assert self.service.is_biblical_answer("") is False


# ===================================================================
# TestGetBibleAnswer
# ===================================================================

class TestGetBibleAnswer:
    """Tests for the public get_bible_answer method."""

    @pytest.mark.asyncio
    async def test_success_returns_answer(self, openai_service):
        """Successful call returns the content string."""
        completion = _make_completion(content="For God so loved the world...")

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.ApiRequestLogRepository") as mock_log_repo,
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_call_repo,
        ):
            result = await openai_service.get_bible_answer("What is John 3:16?", user_id=1, client_ip="127.0.0.1")

        assert result == "For God so loved the world..."
        mock_log_repo.log_request.assert_called_once()
        call_kwargs = mock_log_repo.log_request.call_args
        assert call_kwargs[1]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_with_conversation_history(self, openai_service):
        """Conversation history messages are passed through to the API."""
        completion = _make_completion(content="His ministry began around age 30.")
        captured_kwargs = {}

        async def capture_to_thread(fn, **kwargs):
            captured_kwargs.update(kwargs)
            return completion

        history = [
            {"role": "user", "content": "Who is Jesus?"},
            {"role": "assistant", "content": "Jesus is the Son of God."},
        ]

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=capture_to_thread),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result = await openai_service.get_bible_answer(
                "When did he begin his ministry?",
                conversation_history=history,
            )

        assert result == "His ministry began around age 30."
        # Messages should be: system + 2 history + 1 user question = 4
        messages = captured_kwargs["messages"]
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Who is Jesus?"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "When did he begin his ministry?"

    @pytest.mark.asyncio
    async def test_logs_successful_request(self, openai_service):
        """Successful call logs to ApiRequestLogRepository with status 200."""
        completion = _make_completion(content="Answer here")

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.ApiRequestLogRepository") as mock_log,
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            await openai_service.get_bible_answer("What is faith?", user_id=5, client_ip="10.0.0.1")

        mock_log.log_request.assert_called_once()
        kwargs = mock_log.log_request.call_args[1]
        assert kwargs["user_id"] == 5
        assert kwargs["status_code"] == 200
        assert kwargs["ip_address"] == "10.0.0.1"
        assert kwargs["endpoint"] == "/openai/chat/completions"

    @pytest.mark.asyncio
    async def test_bad_request_error_raises_openai_error(self, openai_service):
        """BadRequestError from OpenAI is converted to OpenAIError."""
        async def raise_bad_request(fn, **kwargs):
            raise _make_bad_request_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_bad_request),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError) as exc_info:
                await openai_service.get_bible_answer("What is faith?")
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_rate_limit_error_raises_openai_error(self, openai_service):
        """RateLimitError from OpenAI is converted to OpenAIError."""
        async def raise_rate_limit(fn, **kwargs):
            raise _make_rate_limit_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_rate_limit),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError) as exc_info:
                await openai_service.get_bible_answer("What is hope?")
            assert "AI service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_timeout_error_raises_openai_error(self, openai_service):
        """APITimeoutError from OpenAI is converted to OpenAIError."""
        async def raise_timeout(fn, **kwargs):
            raise _make_timeout_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_timeout),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError) as exc_info:
                await openai_service.get_bible_answer("What is wisdom?")
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_connection_error_raises_openai_error(self, openai_service):
        """APIConnectionError from OpenAI is converted to OpenAIError."""
        async def raise_connection(fn, **kwargs):
            raise _make_connection_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_connection),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError) as exc_info:
                await openai_service.get_bible_answer("What is grace?")
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_api_error_raises_openai_error(self, openai_service):
        """Generic APIError from OpenAI is converted to OpenAIError."""
        async def raise_api_error(fn, **kwargs):
            raise _make_api_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_api_error),
            patch("app.services.openai_service.ApiRequestLogRepository"),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError) as exc_info:
                await openai_service.get_bible_answer("What is salvation?")
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_logs_failed_request(self, openai_service):
        """Failed API call logs to ApiRequestLogRepository with status 500."""
        async def raise_bad_request(fn, **kwargs):
            raise _make_bad_request_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_bad_request),
            patch("app.services.openai_service.ApiRequestLogRepository") as mock_log,
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError):
                await openai_service.get_bible_answer("What is faith?", user_id=3, client_ip="10.0.0.2")

        mock_log.log_request.assert_called_once()
        kwargs = mock_log.log_request.call_args[1]
        assert kwargs["status_code"] == 500
        assert kwargs["user_id"] == 3

    @pytest.mark.asyncio
    async def test_openai_error_passthrough(self, openai_service):
        """An OpenAIError raised inside _chat_with_tools is re-raised without wrapping."""
        async def raise_openai_error(fn, **kwargs):
            raise OpenAIError("Custom error from inner logic")

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch.object(openai_service, "_chat_with_tools", side_effect=OpenAIError("Custom error")),
            patch("app.services.openai_service.ApiRequestLogRepository"),
        ):
            with pytest.raises(OpenAIError, match="Custom error"):
                await openai_service.get_bible_answer("What is truth?")


# ===================================================================
# TestChatWithTools
# ===================================================================

class TestChatWithTools:
    """Tests for _chat_with_tools (the tool-calling loop)."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_content(self, openai_service):
        """When the model returns content without tool calls, it is returned directly."""
        completion = _make_completion(content="  The answer is 42.  ", finish_reason="stop")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_call_repo,
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], [], user_id=1, question="Q"
            )

        assert result == "The answer is 42."
        mock_call_repo.log_call.assert_called_once()
        call_kwargs = mock_call_repo.log_call.call_args[1]
        assert call_kwargs["status"] == "success"

    @pytest.mark.asyncio
    async def test_with_tool_calls_executes_tools_and_returns_final_answer(self, openai_service):
        """When the model requests tool calls, tools are executed and the final answer is returned."""
        tool_call = _make_tool_call(call_id="call_abc", name="get_verse",
                                    arguments='{"book": "John", "chapter": 3, "verse": 16}')

        # First response: tool call
        first_completion = _make_completion(content=None, tool_calls=[tool_call])
        # Second response: final answer (no tool calls)
        second_completion = _make_completion(content="For God so loved the world...")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_completion
            return second_completion

        tool_result = {"text": "For God so loved the world, that he gave his only begotten Son..."}

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.execute_mcp_tool", return_value=tool_result),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Quote John 3:16"}], [], user_id=1, question="Quote John 3:16"
            )

        assert result == "For God so loved the world..."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_empty_content_raises_openai_error(self, openai_service):
        """Empty content with stop finish_reason raises OpenAIError."""
        completion = _make_completion(content=None, finish_reason="stop")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError, match="empty response"):
                await openai_service._chat_with_tools(
                    [{"role": "user", "content": "Q"}], []
                )

    @pytest.mark.asyncio
    async def test_empty_string_content_raises_openai_error(self, openai_service):
        """Empty string content (after strip) raises OpenAIError."""
        completion = _make_completion(content="", finish_reason="stop")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError, match="empty response"):
                await openai_service._chat_with_tools(
                    [{"role": "user", "content": "Q"}], []
                )

    @pytest.mark.asyncio
    async def test_finish_reason_length_no_content_raises_openai_error(self, openai_service):
        """finish_reason='length' with no content raises a specific OpenAIError about token limit."""
        completion = _make_completion(content=None, finish_reason="length")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError, match="too many verses"):
                await openai_service._chat_with_tools(
                    [{"role": "user", "content": "Q"}], []
                )

    @pytest.mark.asyncio
    async def test_finish_reason_length_with_content_returns_it(self, openai_service):
        """finish_reason='length' with content still returns the content (partial answer)."""
        completion = _make_completion(content="Partial answer here", finish_reason="length")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], []
            )
        assert result == "Partial answer here"

    @pytest.mark.asyncio
    async def test_max_iterations_reached_raises_openai_error(self, openai_service):
        """When the model keeps requesting tool calls beyond max iterations, raises OpenAIError."""
        tool_call = _make_tool_call()

        # Every response has tool calls, never returns a final answer
        completion_with_tools = _make_completion(content=None, tool_calls=[tool_call])

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion_with_tools),
            patch("app.services.openai_service.execute_mcp_tool", return_value={"text": "verse text"}),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError, match="Maximum tool iterations reached"):
                await openai_service._chat_with_tools(
                    [{"role": "user", "content": "Q"}], []
                )

    @pytest.mark.asyncio
    async def test_tool_execution_failure_continues_with_error(self, openai_service):
        """When a tool execution fails, the error is sent back as a tool result and the loop continues."""
        tool_call = _make_tool_call(call_id="call_fail", name="get_verse",
                                    arguments='{"book": "Invalid", "chapter": 0, "verse": 0}')

        first_completion = _make_completion(content=None, tool_calls=[tool_call])
        second_completion = _make_completion(content="Sorry, that verse was not found.")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_completion
            return second_completion

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.execute_mcp_tool", side_effect=Exception("Tool failed")),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Quote Invalid 0:0"}], [], user_id=1, question="Quote Invalid 0:0"
            )

        assert result == "Sorry, that verse was not found."

    @pytest.mark.asyncio
    async def test_logs_successful_call_to_openai_api_call_repository(self, openai_service):
        """A successful completion is logged to OpenAIApiCallRepository with correct token counts."""
        usage = _make_usage(prompt_tokens=80, completion_tokens=200, total_tokens=280)
        completion = _make_completion(content="Answer", usage=usage)

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], [],
                user_id=7, question="What is faith?"
            )

        mock_repo.log_call.assert_called_once()
        kwargs = mock_repo.log_call.call_args[1]
        assert kwargs["user_id"] == 7
        assert kwargs["question"] == "What is faith?"
        assert kwargs["model"] == "gpt-test"
        assert kwargs["prompt_tokens"] == 80
        assert kwargs["completion_tokens"] == 200
        assert kwargs["total_tokens"] == 280
        assert kwargs["status"] == "success"

    @pytest.mark.asyncio
    async def test_accumulates_tokens_across_tool_iterations(self, openai_service):
        """Token counts are accumulated across multiple iterations (tool call + final answer)."""
        tool_call = _make_tool_call()

        usage1 = _make_usage(prompt_tokens=30, completion_tokens=10, total_tokens=40)
        first_completion = _make_completion(content=None, tool_calls=[tool_call], usage=usage1)

        usage2 = _make_usage(prompt_tokens=50, completion_tokens=100, total_tokens=150)
        second_completion = _make_completion(content="Final answer", usage=usage2)

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_completion
            return second_completion

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.execute_mcp_tool", return_value={"text": "verse"}),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], [], user_id=1, question="Q"
            )

        kwargs = mock_repo.log_call.call_args[1]
        assert kwargs["prompt_tokens"] == 80   # 30 + 50
        assert kwargs["completion_tokens"] == 110  # 10 + 100
        assert kwargs["total_tokens"] == 190   # 40 + 150

    @pytest.mark.asyncio
    async def test_no_timeout_when_request_timeout_is_zero(self, openai_service):
        """When request_timeout is 0, asyncio.wait_for is NOT used."""
        openai_service.request_timeout = 0
        completion = _make_completion(content="Answer")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for,
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], []
            )

        assert result == "Answer"
        mock_wait_for.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_response_without_usage_attribute(self, openai_service):
        """Handles response objects that lack a usage attribute gracefully."""
        completion = _make_completion(content="Answer")
        completion.usage = None

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            result = await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], [], user_id=1, question="Q"
            )

        assert result == "Answer"
        # Tokens should all be 0 since usage was None
        kwargs = mock_repo.log_call.call_args[1]
        assert kwargs["prompt_tokens"] == 0
        assert kwargs["completion_tokens"] == 0
        assert kwargs["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_tools_included_in_kwargs_when_provided(self, openai_service):
        """When tools are provided, they are included in the API call kwargs with tool_choice=auto."""
        completion = _make_completion(content="Answer")
        captured_kwargs = {}

        async def capture_to_thread(fn, **kwargs):
            captured_kwargs.update(kwargs)
            return completion

        tools = [{"type": "function", "function": {"name": "get_verse"}}]

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=capture_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], tools
            )

        assert captured_kwargs["tools"] == tools
        assert captured_kwargs["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_no_tools_in_kwargs_when_empty_list(self, openai_service):
        """When tools is an empty list, tools/tool_choice are NOT included in kwargs."""
        completion = _make_completion(content="Answer")
        captured_kwargs = {}

        async def capture_to_thread(fn, **kwargs):
            captured_kwargs.update(kwargs)
            return completion

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=capture_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], []
            )

        assert "tools" not in captured_kwargs
        assert "tool_choice" not in captured_kwargs

    @pytest.mark.asyncio
    async def test_question_truncated_to_500_chars_in_log(self, openai_service):
        """Long questions are truncated to 500 characters in the log entry."""
        completion = _make_completion(content="Answer")
        long_question = "x" * 1000

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": long_question}], [],
                user_id=1, question=long_question
            )

        kwargs = mock_repo.log_call.call_args[1]
        assert len(kwargs["question"]) == 500

    @pytest.mark.asyncio
    async def test_none_question_logged_as_na(self, openai_service):
        """When question is None, it is logged as 'N/A'."""
        completion = _make_completion(content="Answer")

        with (
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            await openai_service._chat_with_tools(
                [{"role": "user", "content": "Q"}], [],
                user_id=1, question=None
            )

        kwargs = mock_repo.log_call.call_args[1]
        assert kwargs["question"] == "N/A"


# ===================================================================
# TestStreamBibleAnswer
# ===================================================================

class TestStreamBibleAnswer:
    """Tests for the public stream_bible_answer method."""

    @pytest.mark.asyncio
    async def test_success_yields_content_chunks(self, openai_service):
        """Streaming without tool calls yields content chunks."""
        # First call (non-streaming) returns no tool calls
        non_stream_completion = _make_completion(content="Not used for streaming", finish_reason="stop")

        # Second call (streaming) returns chunks
        chunk1 = _make_stream_chunk(content="For God ")
        chunk2 = _make_stream_chunk(content="so loved ")
        chunk3 = _make_stream_chunk(content="the world.", finish_reason="stop")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Non-streaming call to detect tool calls
                return non_stream_completion
            else:
                # Streaming call - return iterable of chunks
                return iter([chunk1, chunk2, chunk3])

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            chunks = []
            async for chunk in openai_service.stream_bible_answer("What is John 3:16?"):
                chunks.append(chunk)

        content_chunks = [c for c in chunks if c["type"] == "content"]
        assert len(content_chunks) == 3
        assert content_chunks[0]["text"] == "For God "
        assert content_chunks[1]["text"] == "so loved "
        assert content_chunks[2]["text"] == "the world."

    @pytest.mark.asyncio
    async def test_with_tool_calls_yields_status_then_content(self, openai_service):
        """When tool calls happen, status updates are yielded before content streaming."""
        tool_call = _make_tool_call(call_id="call_1", name="get_verse",
                                    arguments='{"book": "John", "chapter": 3, "verse": 16}')

        # First API call: returns tool calls
        first_completion = _make_completion(content=None, tool_calls=[tool_call])

        # Second API call: no tool calls (non-streaming check)
        second_completion = _make_completion(content="Final answer", finish_reason="stop")

        # Third API call: streaming response
        chunk = _make_stream_chunk(content="Streamed answer", finish_reason="stop")

        call_count = 0

        # Build a proper stream chunk with .choices attribute
        stream_chunk = _make_stream_chunk(content="Streamed answer", finish_reason="stop")

        async def mock_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First non-streaming API call: returns tool calls
                return first_completion
            elif call_count == 2:
                # Tool execution: to_thread(execute_mcp_tool, name, args)
                return {"text": "verse text"}
            elif call_count == 3:
                # Second non-streaming API call: no tool calls
                return second_completion
            else:
                # Streaming call: returns iterable of chunk objects
                return [stream_chunk]

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.execute_mcp_tool", return_value={"text": "verse text"}),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            result_chunks = []
            async for c in openai_service.stream_bible_answer("Quote John 3:16"):
                result_chunks.append(c)

        # Should have: status (looking up), status (generating), then content
        status_chunks = [c for c in result_chunks if c["type"] == "status"]
        content_chunks = [c for c in result_chunks if c["type"] == "content"]
        assert len(status_chunks) >= 2
        assert "Looking up Bible verses" in status_chunks[0]["message"]
        assert "Generating answer" in status_chunks[1]["message"]
        assert len(content_chunks) >= 1

    @pytest.mark.asyncio
    async def test_bad_request_error_raises_openai_error(self, openai_service):
        """BadRequestError during streaming raises OpenAIError."""
        async def raise_bad_request(fn, **kwargs):
            raise _make_bad_request_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_bad_request),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError):
                async for _ in openai_service.stream_bible_answer("What is faith?"):
                    pass

    @pytest.mark.asyncio
    async def test_rate_limit_error_raises_openai_error(self, openai_service):
        """RateLimitError during streaming raises OpenAIError."""
        async def raise_rate_limit(fn, **kwargs):
            raise _make_rate_limit_error()

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=raise_rate_limit),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError):
                async for _ in openai_service.stream_bible_answer("What is hope?"):
                    pass

    @pytest.mark.asyncio
    async def test_openai_error_passthrough(self, openai_service):
        """An OpenAIError raised inside _stream_chat_with_tools is re-raised."""
        async def mock_stream(*args, **kwargs):
            raise OpenAIError("inner error")
            yield  # makes this an async generator  # pragma: no cover

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch.object(openai_service, "_stream_chat_with_tools", side_effect=mock_stream),
        ):
            with pytest.raises(OpenAIError, match="inner error"):
                async for _ in openai_service.stream_bible_answer("Q"):
                    pass

    @pytest.mark.asyncio
    async def test_finish_reason_length_yields_truncation_error(self, openai_service):
        """When streaming finishes with reason 'length', an error chunk is yielded."""
        non_stream_completion = _make_completion(content="Not used", finish_reason="stop")

        chunk1 = _make_stream_chunk(content="Partial...")
        chunk2 = _make_stream_chunk(finish_reason="length")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_stream_completion
            else:
                return iter([chunk1, chunk2])

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            chunks = []
            async for chunk in openai_service.stream_bible_answer("Tell me everything about Genesis"):
                chunks.append(chunk)

        error_chunks = [c for c in chunks if c.get("type") == "error"]
        assert len(error_chunks) == 1
        assert "truncated" in error_chunks[0]["message"].lower()

    @pytest.mark.asyncio
    async def test_stream_logs_to_openai_api_call_repository(self, openai_service):
        """Streaming completion logs to OpenAIApiCallRepository on success."""
        non_stream_completion = _make_completion(content="Not used", finish_reason="stop")

        stream_usage = _make_usage(prompt_tokens=20, completion_tokens=50, total_tokens=70)
        chunk1 = _make_stream_chunk(content="Hello")
        chunk2 = _make_stream_chunk(finish_reason="stop", usage=stream_usage)

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_stream_completion
            else:
                return iter([chunk1, chunk2])

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            async for _ in openai_service.stream_bible_answer("What is love?", user_id=10):
                pass

        mock_repo.log_call.assert_called()
        kwargs = mock_repo.log_call.call_args[1]
        assert kwargs["status"] == "success"

    @pytest.mark.asyncio
    async def test_stream_max_iterations_raises_openai_error(self, openai_service):
        """When streaming keeps hitting tool calls beyond max iterations, raises OpenAIError."""
        tool_call = _make_tool_call()
        completion_with_tools = _make_completion(content=None, tool_calls=[tool_call])

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", new_callable=AsyncMock, return_value=completion_with_tools),
            patch("app.services.openai_service.execute_mcp_tool", return_value={"text": "verse"}),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            with pytest.raises(OpenAIError, match="Maximum tool iterations reached"):
                async for _ in openai_service.stream_bible_answer("Q"):
                    pass

    @pytest.mark.asyncio
    async def test_stream_with_conversation_history(self, openai_service):
        """Conversation history is included in streaming requests."""
        non_stream_completion = _make_completion(content="Not used", finish_reason="stop")
        chunk = _make_stream_chunk(content="Answer", finish_reason="stop")

        captured_kwargs = {}
        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count, captured_kwargs
            call_count += 1
            if call_count == 1:
                captured_kwargs.update(kwargs)
                return non_stream_completion
            return iter([chunk])

        history = [{"role": "user", "content": "Previous question"}]

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            async for _ in openai_service.stream_bible_answer("Follow up", conversation_history=history):
                pass

        messages = captured_kwargs["messages"]
        # system + 1 history + 1 user = 3
        assert len(messages) == 3
        assert messages[1]["content"] == "Previous question"

    @pytest.mark.asyncio
    async def test_stream_completes_without_finish_reason(self, openai_service):
        """When streaming ends without a finish_reason chunk, it still logs and returns gracefully."""
        non_stream_completion = _make_completion(content="Not used", finish_reason="stop")

        # A chunk with content but no finish_reason, and then the iterator ends
        chunk1 = _make_stream_chunk(content="Some content")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_stream_completion
            return iter([chunk1])

        with (
            patch("app.services.openai_service.get_bible_tools_for_openai", return_value=[]),
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            chunks = []
            async for chunk in openai_service.stream_bible_answer("Q"):
                chunks.append(chunk)

        # Should still log even without finish_reason
        mock_repo.log_call.assert_called()
        content_chunks = [c for c in chunks if c["type"] == "content"]
        assert len(content_chunks) == 1


# ===================================================================
# TestStreamChatWithTools
# ===================================================================

class TestStreamChatWithTools:
    """Tests for _stream_chat_with_tools (the streaming tool-calling loop)."""

    @pytest.mark.asyncio
    async def test_tool_execution_failure_continues_with_error_result(self, openai_service):
        """When a tool fails during streaming, the error is captured and sent back as a tool result."""
        tool_call = _make_tool_call(call_id="call_err", name="get_verse",
                                    arguments='{"book": "Bad", "chapter": 1, "verse": 1}')

        first_completion = _make_completion(content=None, tool_calls=[tool_call])
        second_completion = _make_completion(content="Could not find that verse.", finish_reason="stop")
        stream_chunk = _make_stream_chunk(content="Could not find that verse.", finish_reason="stop")

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_completion
            elif call_count == 2:
                return second_completion
            return iter([stream_chunk])

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.execute_mcp_tool", side_effect=ValueError("Not found")),
            patch("app.services.openai_service.OpenAIApiCallRepository"),
        ):
            chunks = []
            async for chunk in openai_service._stream_chat_with_tools(
                [{"role": "user", "content": "Q"}], []
            ):
                chunks.append(chunk)

        status_chunks = [c for c in chunks if c["type"] == "status"]
        assert len(status_chunks) >= 1

    @pytest.mark.asyncio
    async def test_stream_usage_accumulated_from_final_chunk(self, openai_service):
        """Stream usage from the final chunk is accumulated into the log."""
        non_stream_usage = _make_usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        non_stream_completion = _make_completion(content="check", finish_reason="stop", usage=non_stream_usage)

        stream_usage = _make_usage(prompt_tokens=30, completion_tokens=40, total_tokens=70)
        chunk1 = _make_stream_chunk(content="Answer")
        chunk2 = _make_stream_chunk(finish_reason="stop", usage=stream_usage)

        call_count = 0

        async def mock_to_thread(fn, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return non_stream_completion
            return iter([chunk1, chunk2])

        with (
            patch("app.services.openai_service.asyncio.to_thread", side_effect=mock_to_thread),
            patch("app.services.openai_service.OpenAIApiCallRepository") as mock_repo,
        ):
            async for _ in openai_service._stream_chat_with_tools(
                [{"role": "user", "content": "Q"}], [],
                user_id=1, question="Q"
            ):
                pass

        kwargs = mock_repo.log_call.call_args[1]
        # Accumulated: non-stream + stream usage
        assert kwargs["prompt_tokens"] == 40   # 10 + 30
        assert kwargs["completion_tokens"] == 45  # 5 + 40
        assert kwargs["total_tokens"] == 85   # 15 + 70


# ===================================================================
# TestNormalizeHistory
# ===================================================================

class TestNormalizeHistory:
    """Tests for _normalize_history."""

    def test_normal_list_of_messages(self, openai_service):
        """A normal list of dict messages is normalized to role/content format."""
        history = [
            {"role": "user", "content": "Who is Moses?"},
            {"role": "assistant", "content": "Moses led the Israelites out of Egypt."},
        ]
        result = openai_service._normalize_history(history)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Who is Moses?"}
        assert result[1] == {"role": "assistant", "content": "Moses led the Israelites out of Egypt."}

    def test_history_exceeding_max_is_truncated(self, openai_service):
        """History longer than max_history_messages is truncated to keep the most recent."""
        openai_service.max_history_messages = 2
        history = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "Third"},
            {"role": "assistant", "content": "Fourth"},
        ]
        result = openai_service._normalize_history(history)

        assert len(result) == 2
        assert result[0]["content"] == "Third"
        assert result[1]["content"] == "Fourth"

    def test_empty_history_returns_empty_list(self, openai_service):
        """Empty list input returns an empty list."""
        assert openai_service._normalize_history([]) == []

    def test_none_history_returns_empty_list(self, openai_service):
        """None input returns an empty list."""
        assert openai_service._normalize_history(None) == []

    def test_non_string_content_gets_converted(self, openai_service):
        """Non-string content values are converted to strings."""
        history = [{"role": "assistant", "content": {"key": "value"}}]
        result = openai_service._normalize_history(history)

        assert result[0]["content"] == "{'key': 'value'}"
        assert isinstance(result[0]["content"], str)

    def test_integer_content_gets_converted(self, openai_service):
        """Integer content is converted to string."""
        history = [{"role": "user", "content": 42}]
        result = openai_service._normalize_history(history)

        assert result[0]["content"] == "42"

    def test_none_content_gets_converted(self, openai_service):
        """None content uses the empty string default."""
        history = [{"role": "user", "content": None}]
        result = openai_service._normalize_history(history)

        # _get_message_field returns "" as default when value is None
        assert result[0]["content"] == ""

    def test_missing_role_defaults_to_user(self, openai_service):
        """Messages without a role field default to 'user'."""
        history = [{"content": "No role here"}]
        result = openai_service._normalize_history(history)

        assert result[0]["role"] == "user"

    def test_object_messages_supported(self, openai_service):
        """History entries provided as objects (e.g., Pydantic models) are supported."""

        class Msg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        history = [Msg("assistant", "Typed message")]
        result = openai_service._normalize_history(history)

        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Typed message"

    def test_max_history_zero_means_no_limit(self, openai_service):
        """When max_history_messages is 0, no truncation occurs."""
        openai_service.max_history_messages = 0
        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = openai_service._normalize_history(history)

        assert len(result) == 20

    def test_exact_max_not_truncated(self, openai_service):
        """History at exactly the max limit is not truncated."""
        openai_service.max_history_messages = 3
        history = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ]
        result = openai_service._normalize_history(history)

        assert len(result) == 3


# ===================================================================
# TestGetMessageField
# ===================================================================

class TestGetMessageField:
    """Tests for _get_message_field."""

    def test_from_dict(self, openai_service):
        """Retrieves a field from a plain dict."""
        msg = {"role": "user", "content": "Hello"}
        assert openai_service._get_message_field(msg, "role") == "user"
        assert openai_service._get_message_field(msg, "content") == "Hello"

    def test_from_dict_missing_key_returns_default(self, openai_service):
        """Missing key in a dict returns the provided default."""
        msg = {"role": "user"}
        assert openai_service._get_message_field(msg, "content", "fallback") == "fallback"

    def test_from_object_with_attributes(self, openai_service):
        """Retrieves a field from an object with attributes (no .get method)."""

        class Msg:
            def __init__(self):
                self.role = "assistant"
                self.content = "World"

        msg = Msg()
        assert openai_service._get_message_field(msg, "role") == "assistant"
        assert openai_service._get_message_field(msg, "content") == "World"

    def test_from_object_missing_attribute_returns_default(self, openai_service):
        """Missing attribute on an object returns the default."""

        class Msg:
            role = "user"

        msg = Msg()
        assert openai_service._get_message_field(msg, "content", "default_val") == "default_val"

    def test_from_pydantic_model_with_model_dump(self, openai_service):
        """Falls through to model_dump() when primary access returns the default."""

        class FakeModel:
            def get(self, key, default=None):
                # Simulates a dict-like that doesn't have the field
                return default

            def model_dump(self):
                return {"role": "system", "content": "From model_dump"}

        msg = FakeModel()
        assert openai_service._get_message_field(msg, "content", "") == "From model_dump"

    def test_model_dump_used_when_getattr_returns_none(self, openai_service):
        """model_dump is consulted when the primary accessor returns None."""

        class FakeModel:
            role = None

            def model_dump(self):
                return {"role": "assistant"}

        msg = FakeModel()
        assert openai_service._get_message_field(msg, "role", "") == "assistant"

    def test_default_value_returned_when_value_is_none(self, openai_service):
        """If all accessors yield None and no model_dump exists, default is returned."""

        class Empty:
            pass

        msg = Empty()
        assert openai_service._get_message_field(msg, "anything", "my_default") == "my_default"

    def test_model_dump_non_dict_returns_previous_value(self, openai_service):
        """If model_dump() returns a non-dict, the value from getattr is preserved."""

        class WeirdModel:
            content = "from_attr"

            def model_dump(self):
                return "not a dict"

        msg = WeirdModel()
        assert openai_service._get_message_field(msg, "content", "") == "from_attr"

    def test_dict_with_none_value_returns_default(self, openai_service):
        """A dict key explicitly set to None should return the default."""
        msg = {"role": "user", "content": None}
        assert openai_service._get_message_field(msg, "content", "fallback") == "fallback"

    def test_dict_get_returns_actual_value(self, openai_service):
        """Ordinary dict access returns the actual stored value."""
        msg = {"role": "user", "content": "actual"}
        assert openai_service._get_message_field(msg, "content", "fallback") == "actual"


# ===================================================================
# TestInit
# ===================================================================

class TestInit:
    """Tests for OpenAIService.__init__ configuration."""

    def test_reads_settings_from_get_settings(self):
        """__init__ reads all configuration from get_settings()."""
        with patch("app.config.get_settings") as mock_get_settings:
            settings = mock_get_settings.return_value
            settings.openai_api_key = "sk-test-key"
            settings.openai_model = "gpt-4o"
            settings.openai_max_output_tokens = 2000
            settings.openai_request_timeout = 60
            settings.openai_max_history_messages = 20

            service = OpenAIService()

        assert service.model == "gpt-4o"
        assert service.max_tokens == 2000
        assert service.request_timeout == 60
        assert service.max_history_messages == 20
        assert service.max_tool_iterations == 2

    def test_max_tokens_minimum_is_one(self):
        """max_tokens enforces a minimum of 1."""
        with patch("app.config.get_settings") as mock_get_settings:
            settings = mock_get_settings.return_value
            settings.openai_api_key = "sk-test"
            settings.openai_model = "gpt-test"
            settings.openai_max_output_tokens = -5
            settings.openai_request_timeout = 30
            settings.openai_max_history_messages = 10

            service = OpenAIService()

        assert service.max_tokens == 1

    def test_request_timeout_minimum_is_zero(self):
        """request_timeout enforces a minimum of 0."""
        with patch("app.config.get_settings") as mock_get_settings:
            settings = mock_get_settings.return_value
            settings.openai_api_key = "sk-test"
            settings.openai_model = "gpt-test"
            settings.openai_max_output_tokens = 100
            settings.openai_request_timeout = -10
            settings.openai_max_history_messages = 10

            service = OpenAIService()

        assert service.request_timeout == 0

    def test_max_history_messages_minimum_is_zero(self):
        """max_history_messages enforces a minimum of 0."""
        with patch("app.config.get_settings") as mock_get_settings:
            settings = mock_get_settings.return_value
            settings.openai_api_key = "sk-test"
            settings.openai_model = "gpt-test"
            settings.openai_max_output_tokens = 100
            settings.openai_request_timeout = 30
            settings.openai_max_history_messages = -3

            service = OpenAIService()

        assert service.max_history_messages == 0
