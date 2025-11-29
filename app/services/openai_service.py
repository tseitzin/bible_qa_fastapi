"""OpenAI service for handling AI completions."""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
        self.max_tool_iterations = 2  # Limit to 2 rounds - most questions only need 1

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
    
    async def stream_bible_answer(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ):
        """Stream an AI-generated answer to a Bible-related question.
        
        Yields status updates during tool execution and streams the final answer.
        """
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
            async for chunk in self._stream_chat_with_tools(messages, tools):
                yield chunk
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
        import time
        
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # Make API request
            start_time = time.time()
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": self.max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            task = asyncio.to_thread(self.client.chat.completions.create, **kwargs)
            if self.request_timeout > 0:
                response = await asyncio.wait_for(task, timeout=self.request_timeout)
            else:
                response = await task
            
            elapsed = time.time() - start_time
            logger.info(f"OpenAI API call completed in {elapsed:.2f}s (iteration {iteration})")
            
            message = response.choices[0].message
            
            # If no tool calls, return the answer
            if not message.tool_calls:
                content = message.content
                finish_reason = response.choices[0].finish_reason
                logger.info(f"OpenAI response (no tool calls): content={content}, finish_reason={finish_reason}")
                
                # Handle token limit reached
                if finish_reason == "length" and not content:
                    logger.warning("OpenAI hit token limit. This usually happens when the question is too broad.")
                    raise OpenAIError("The answer requires too many verses to fit in one response. Please try asking a more specific question.")
                
                if not content:
                    logger.error(f"Empty response from OpenAI. Full message: {message.model_dump()}")
                    raise OpenAIError("AI service returned an empty response")
                return content.strip()
            
            # Add assistant's message with tool calls to history
            messages.append(message.model_dump())
            
            # Execute tool calls in parallel for speed
            async def execute_tool_async(tool_call):
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing MCP tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_result = await asyncio.to_thread(execute_mcp_tool, tool_name, tool_args)
                    result_content = json.dumps(tool_result)
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    result_content = json.dumps({"error": str(e)})
                
                return {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content
                }
            
            # Execute all tool calls in parallel
            tool_results = await asyncio.gather(*[execute_tool_async(tc) for tc in message.tool_calls])
            
            # Add all tool results to messages
            messages.extend(tool_results)
        
        raise OpenAIError("Maximum tool iterations reached")
    
    async def _stream_chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """Execute a streaming chat completion with function calling support.
        
        Yields status updates during tool execution and streams the final answer tokens.
        """
        import time
        
        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # Make initial API request (non-streaming to detect tool calls)
            start_time = time.time()
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": self.max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            task = asyncio.to_thread(self.client.chat.completions.create, **kwargs)
            if self.request_timeout > 0:
                response = await asyncio.wait_for(task, timeout=self.request_timeout)
            else:
                response = await task
            
            elapsed = time.time() - start_time
            logger.info(f"OpenAI API call completed in {elapsed:.2f}s (iteration {iteration})")
            
            message = response.choices[0].message
            
            # If tool calls are needed, execute them and continue (no streaming yet)
            if message.tool_calls:
                # Yield status update
                tool_names = [tc.function.name for tc in message.tool_calls]
                yield {"type": "status", "message": f"Looking up Bible verses ({len(message.tool_calls)})..."}
                
                # Add assistant's message with tool calls to history
                messages.append(message.model_dump())
                
                # Execute tool calls in parallel
                async def execute_tool_async(tool_call):
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Executing MCP tool: {tool_name} with args: {tool_args}")
                    
                    try:
                        tool_result = await asyncio.to_thread(execute_mcp_tool, tool_name, tool_args)
                        result_content = json.dumps(tool_result)
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        result_content = json.dumps({"error": str(e)})
                    
                    return {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content
                    }
                
                # Execute all tool calls in parallel
                tool_results = await asyncio.gather(*[execute_tool_async(tc) for tc in message.tool_calls])
                
                # Add all tool results to messages
                messages.extend(tool_results)
                
                # Yield status that we're generating the answer
                yield {"type": "status", "message": "Generating answer..."}
                
                # Continue loop to get final answer with streaming
                continue
            
            # No tool calls - this is the final answer, stream it
            # Make streaming request for the final answer
            kwargs["stream"] = True
            
            stream_task = asyncio.to_thread(self.client.chat.completions.create, **kwargs)
            if self.request_timeout > 0:
                stream = await asyncio.wait_for(stream_task, timeout=self.request_timeout)
            else:
                stream = await stream_task
            
            # Stream tokens
            content_started = False
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        if not content_started:
                            content_started = True
                        yield {"type": "content", "text": delta.content}
                    
                    # Check for finish
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                        if finish_reason == "length":
                            logger.warning("OpenAI hit token limit during streaming")
                            yield {"type": "error", "message": "Response truncated due to length"}
                        return
            
            # If we got here, streaming completed successfully
            return
        
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
