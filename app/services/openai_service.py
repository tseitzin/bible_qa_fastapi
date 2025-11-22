"""OpenAI service for handling AI completions."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


NON_BIBLICAL_RESPONSE = (
    "This app is only for researching and asking questions about God's word. "
    "Please ask a Bible-related question."
)

SYSTEM_PROMPT = (
    "You are a helpful Bible scholar with deep knowledge of Christian theology, "
    "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
    "and biblically-grounded answers. When appropriate, include relevant scripture "
    "references. Be respectful of different denominational perspectives. "
    "When answering follow-up questions, maintain context from the previous conversation "
    "and provide deeper insights or additional details as requested. "
    "Only answer questions that clearly relate to the Bible or Christian faith. "
    f"If a user asks about something unrelated to God's word, respond with: '{NON_BIBLICAL_RESPONSE}'"
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
        self.request_timeout = max(0, settings.openai_request_timeout)
        self.max_history_messages = max(0, settings.openai_max_history_messages)

        effort = (settings.openai_reasoning_effort or "").strip().lower()
        self.reasoning_effort = effort if effort in {"none", "low", "medium", "high"} else "low"

    async def get_bible_answer(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Get an AI-generated answer to a Bible-related question."""

        history_variants = self._build_history_variants(conversation_history)
        token_limit = max(1, self.max_output_tokens)
        timeout_exc: Optional[asyncio.TimeoutError] = None

        for attempt_index, history_messages in enumerate(history_variants, start=1):
            messages = [self._build_message("system", SYSTEM_PROMPT)]
            if history_messages:
                messages.extend(history_messages)
            messages.append(self._build_message("user", question))

            try:
                response = await self._send_with_truncation_retry(messages, token_limit)
            except asyncio.TimeoutError as exc:
                timeout_exc = exc
                logger.warning(
                    "OpenAI request timed out (attempt %s/%s, history_len=%s)",
                    attempt_index,
                    len(history_variants),
                    len(history_messages),
                )
                continue
            except (BadRequestError, RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
                logger.error("OpenAI API error: %s", exc)
                raise OpenAIError("AI service unavailable") from exc
            except OpenAIError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Unexpected OpenAI failure")
                raise OpenAIError("AI service unavailable") from exc

            answer = self._extract_text(response)
            if not answer:
                logger.error(
                    "OpenAI returned an empty response: %s",
                    getattr(response, "model_dump", lambda: response)(),
                )
                raise OpenAIError("AI service returned an empty response")

            return answer

        if timeout_exc:
            timeout_label = f"{self.request_timeout} seconds" if self.request_timeout else "the configured deadline"
            logger.error("OpenAI request timed out after %s", timeout_label)
            raise OpenAIError("AI service timed out") from timeout_exc

        raise OpenAIError("AI service unavailable")

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
            role = self._get_message_field(message, "role", "user") or "user"
            content = self._get_message_field(message, "content", "")
            if not isinstance(content, str):
                content = str(content)
            normalized.append(self._build_message(role, content))
        return normalized

    def _get_message_field(self, message: Any, field: str, default: str = "") -> str:
        """Retrieve a field from dicts, Pydantic models, or simple objects."""

        getter = getattr(message, "get", None)
        if callable(getter):
            value = getter(field, default)
        else:
            value = getattr(message, field, default)

        if (value is None or value == default) and hasattr(message, "model_dump"):
            dumped = message.model_dump()
            if isinstance(dumped, dict):
                value = dumped.get(field, value)

        return default if value is None else value

    def _build_history_variants(
        self, conversation_history: Optional[Iterable[Dict[str, Any]]]
    ) -> List[List[Dict[str, Any]]]:
        """Prepare progressively trimmed history variants for retry attempts."""

        history_list = list(conversation_history or [])
        if self.max_history_messages > 0 and len(history_list) > self.max_history_messages:
            history_list = history_list[-self.max_history_messages :]

        variants: List[List[Dict[str, Any]]] = []
        seen_signatures: set[Tuple[Tuple[str, str], ...]] = set()

        def add_variant(raw_history: Iterable[Dict[str, Any]]):
            normalized = self._normalize_history(raw_history)
            signature = tuple(
                (
                    message["role"],
                    tuple(part.get("text", "") for part in message.get("content", [])),
                )
                for message in normalized
            )
            if signature in seen_signatures:
                return
            seen_signatures.add(signature)
            variants.append(normalized)

        if history_list:
            add_variant(history_list)
            if len(history_list) > 2:
                half_window = max(2, len(history_list) // 2)
                add_variant(history_list[-half_window:])

        add_variant([])

        return variants

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

        task = asyncio.to_thread(self.client.responses.create, **kwargs)
        if self.request_timeout > 0:
            return await asyncio.wait_for(task, timeout=self.request_timeout)
        return await task

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

    def is_biblical_answer(self, answer: Optional[str]) -> bool:
        """Determine if an AI answer reflects a Bible-related response."""

        if not answer:
            return False

        normalized = answer.strip()
        if not normalized:
            return False

        if NON_BIBLICAL_RESPONSE.lower() in normalized.lower():
            return False

        return True

    async def _send_with_truncation_retry(
        self,
        messages: List[Dict[str, Any]],
        token_limit: int,
    ):
        """Send a request and optionally retry if the response is truncated."""

        response = await self._request_response(messages, token_limit)

        if (
            self.retry_on_truncation
            and self.retry_max_output_tokens > token_limit
            and self._is_truncated(response)
        ):
            logger.info(
                "OpenAI response truncated at %s tokens; retrying with %s max tokens",
                token_limit,
                self.retry_max_output_tokens,
            )
            response = await self._request_response(messages, self.retry_max_output_tokens)

        return response
