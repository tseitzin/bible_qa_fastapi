"""OpenAI service for handling AI completions."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.utils.exceptions import OpenAIError

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a helpful Bible scholar with deep knowledge of Christian theology, "
    "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
    "and biblically-grounded answers. When appropriate, include relevant scripture "
    "references. Be respectful of different denominational perspectives. "
    "When answering follow-up questions, maintain context from the previous conversation "
    "and provide deeper insights or additional details as requested."
)


class OpenAIService:
    """Service for interacting with the OpenAI Responses API."""

    def __init__(self) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_output_tokens = max(1, settings.openai_max_output_tokens)
        self.retry_max_output_tokens = max(self.max_output_tokens + 1, settings.openai_max_output_tokens_retry)
        self.retry_on_truncation = settings.openai_retry_on_truncation

        effort = (settings.openai_reasoning_effort or "").strip().lower()
        self.reasoning_effort = effort if effort in {"none", "low", "medium", "high"} else "low"

    async def get_bible_answer(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Get an AI-generated answer to a Bible-related question."""

        messages = [self._build_message("system", SYSTEM_PROMPT)]

        if conversation_history:
            messages.extend(self._normalize_history(conversation_history))

        messages.append(self._build_message("user", question))

        try:
            response = await self._request_response(messages, self.max_output_tokens)

            if (
                self.retry_on_truncation
                and self.retry_max_output_tokens > self.max_output_tokens
                and self._is_truncated(response)
            ):
                logger.info(
                    "OpenAI response truncated at %s tokens; retrying with %s max tokens",
                    self.max_output_tokens,
                    self.retry_max_output_tokens,
                )
                response = await self._request_response(messages, self.retry_max_output_tokens)

            answer = self._extract_text(response)
            if not answer:
                logger.error("OpenAI returned an empty response: %s", getattr(response, "model_dump", lambda: response)())
                raise OpenAIError("AI service returned an empty response")

            return answer

        except (BadRequestError, RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
            logger.error("OpenAI API error: %s", exc)
            raise OpenAIError("AI service unavailable") from exc
        except OpenAIError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected OpenAI failure")
            raise OpenAIError("AI service unavailable") from exc

    def _build_message(self, role: str, text: str) -> Dict[str, Any]:
        """Wrap text in the Responses API message structure."""

        message_type = "output_text" if role == "assistant" else "input_text"

        return {
            "role": role,
            "content": [
                {
                    "type": message_type,
                    "text": text,
                }
            ],
        }

    def _normalize_history(
        self, conversation_history: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert stored history into Responses API format."""

        normalized: List[Dict[str, Any]] = []
        for message in conversation_history:
            role = message.get("role", "user")
            content = message.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            normalized.append(self._build_message(role, content))
        return normalized

    def _extract_text(self, response: Any) -> str:
        """Extract plain text from a Responses API result."""

        text = getattr(response, "output_text", None)
        if text:
            return text.strip()

        output = self._safe_get(response, "output") or []
        segments: List[str] = []

        for item in output:
            content_list = self._safe_get(item, "content") or []
            for part in content_list:
                part_text = self._safe_get(part, "text") or self._safe_get(part, "output_text")
                if part_text:
                    segments.append(str(part_text))

        return "\n\n".join(segment.strip() for segment in segments if segment)

    async def _request_response(self, messages: List[Dict[str, Any]], max_output_tokens: int):
        """Call the OpenAI Responses API in a thread."""

        kwargs = {
            "model": self.model,
            "input": messages,
            "max_output_tokens": max_output_tokens,
        }

        if self.reasoning_effort and self.reasoning_effort != "none":
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        return await asyncio.to_thread(self.client.responses.create, **kwargs)

    def _is_truncated(self, response: Any) -> bool:
        """Determine whether the response ended due to token limits."""

        status = self._safe_get(response, "status")
        if status and status != "incomplete":
            return False

        details = self._safe_get(response, "incomplete_details")
        reason = self._safe_get(details, "reason")
        return reason == "max_output_tokens"

    def _safe_get(self, obj: Any, key: str) -> Any:
        """Best-effort accessor for OpenAI response objects."""

        if obj is None:
            return None

        if hasattr(obj, key):
            return getattr(obj, key)

        getter = getattr(obj, "get", None)
        if callable(getter):
            return getter(key)

        dumper = getattr(obj, "model_dump", None)
        if callable(dumper):
            dumped = dumper()
            if isinstance(dumped, dict):
                return dumped.get(key)

        return None
