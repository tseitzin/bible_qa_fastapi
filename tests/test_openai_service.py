"""Unit tests for the OpenAI service."""
import pytest
from unittest.mock import patch

from app.services.openai_service import OpenAIService, NON_BIBLICAL_RESPONSE


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


# NOTE: Other test classes removed (TestGetBibleAnswer, TestExtractText, etc.)
# These tested private implementation details (_request_response, _extract_text,
# _normalize_history, _safe_get) that were refactored out when the OpenAI SDK
# was updated to use the new tool-calling API. The public methods are tested
# through integration tests in test_question_service.py.
