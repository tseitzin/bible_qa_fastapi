"""OpenAI service for handling AI completions."""
from __future__ import annotations

import asyncio
import json
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
from app.services.mcp_integration import execute_mcp_tool, get_bible_tools_for_openai

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
    "\n\nIMPORTANT: You have access to tools that retrieve verses from the King James Version Bible database. "
    "ALWAYS use these tools when you need to cite or quote Bible verses. NEVER quote verses from memory. "
    "Use get_verse for single verses, get_passage for verse ranges, get_chapter for full chapters, "
    "and search_verses to find verses containing specific keywords. "
    "\n\nOnly answer questions that clearly relate to the Bible or Christian faith. "
    f"If a user asks about something unrelated to God's word, respond with: '{NON_BIBLICAL_RESPONSE}'"
)


class OpenAIService:
    """Service for interacting with the OpenAI Chat Completions API."""

    def __init__(self) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = max(1, settings.openai_max_output_tokens)
        self.request_timeout = max(0, settings.openai_request_timeout)
        self.max_history_messages = max(0, settings.openai_max_history_messages)
        self.max_tool_iterations = 10  # Prevent infinite loops

    async def get_bible_answer(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Get an AI-generated answer to a Bible-related question using Chat Completions with function calling."""
        
        # Build message list for Chat Completions API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add conversation history if provided
        if conversation_history:
            history = self._normalize_history(conversation_history)
            messages.extend(history)
        
        # Add the user's question
        messages.append({"role": "user", "content": question})
        
        # Get available Bible tools
        tools = get_bible_tools_for_openai()
        
        try:
            answer = await self._chat_with_tools(messages, tools)
            return answer
        except (BadRequestError, RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
            logger.error("OpenAI API error: %s", exc)
            raise OpenAIError("AI service unavailable") from exc
        except OpenAIError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected OpenAI failure")
            raise OpenAIError("AI service unavailable") from exc

    async def _chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> str:
        """Execute a chat completion with function calling support."""
        
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # Make API request
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            task = asyncio.to_thread(self.client.chat.completions.create, **kwargs)
            if self.request_timeout > 0:
                response = await asyncio.wait_for(task, timeout=self.request_timeout)
            else:
                response = await task
            
            message = response.choices[0].message
            
            # If no tool calls, return the answer
            if not message.tool_calls:
                content = message.content
                if not content:
                    raise OpenAIError("AI service returned an empty response")
                return content.strip()
            
            # Add assistant's message with tool calls to history
            messages.append(message.model_dump())
            
            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing MCP tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_result = execute_mcp_tool(tool_name, tool_args)
                    result_content = json.dumps(tool_result)
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    result_content = json.dumps({"error": str(e)})
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content
                })
        
        raise OpenAIError("Maximum tool iterations reached")
    
    def _normalize_history(
        self, conversation_history: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert stored history into Chat Completions format."""
        normalized: List[Dict[str, Any]] = []
        history_list = list(conversation_history or [])
        
        # Limit history if configured
        if self.max_history_messages > 0 and len(history_list) > self.max_history_messages:
            history_list = history_list[-self.max_history_messages:]
        
        for message in history_list:
            role = self._get_message_field(message, "role", "user") or "user"
            content = self._get_message_field(message, "content", "")
            if not isinstance(content, str):
                content = str(content)
            normalized.append({"role": role, "content": content})
        
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
