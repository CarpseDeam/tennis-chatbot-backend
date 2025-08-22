# core/llm/deepseek_service.py
import logging
import json
from typing import List, AsyncGenerator
from openai import AsyncOpenAI

from .base import LLMService
from config import settings
from schemas.chat_schemas import ChatMessage
from core.tools.web_search import google_search, SEARCH_TOOL_SCHEMA

logger = logging.getLogger(__name__)


class DeepSeekService(LLMService):
    """LLM Service for DeepSeek, with streaming and tool-calling."""

    def __init__(self):
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set in the environment.")

        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model_name = settings.deepseek_model_name
        logger.info(f"DeepSeek service initialized in TOOL-CALLING mode with model: {self.model_name}")

    def _convert_history(self, history: List[ChatMessage]) -> List[dict]:
        """Converts internal ChatMessage format to OpenAI's message format."""
        messages = [{
            "role": "system",
            "content": "You are a world-class tennis expert. Use the `web_search` tool to find current information to answer user questions."
        }]
        for msg in history:
            role = "assistant" if msg.role.lower() in ["assistant", "model"] else "user"
            messages.append({"role": role, "content": msg.content})
        return messages

    async def generate_response_async(self, query: str, history: List[ChatMessage]) -> AsyncGenerator[str, None]:
        """Generates a streaming response, handling the tool-calling loop."""
        messages = self._convert_history(history)
        messages.append({"role": "user", "content": query})

        # First, a non-streaming call to check for tool usage efficiently.
        first_response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=[{"type": "function", "function": SEARCH_TOOL_SCHEMA}]
        )
        response_message = first_response.choices[0].message
        messages.append(response_message)

        # Determine the next step based on the model's response.
        stream_request_messages = messages

        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "web_search":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    search_query = arguments.get("query")
                except json.JSONDecodeError:
                    yield "I had an issue understanding what to search for."
                    return

                logger.info(f"DeepSeek requested tool call: web_search(query='{search_query}')")
                tool_response_content = await google_search(search_query)

                # Prepare the messages for the final streaming call
                stream_request_messages.append({
                    "tool_call_id": tool_call.id, "role": "tool",
                    "name": "web_search", "content": tool_response_content,
                })

        # The final call is ALWAYS a streaming call.
        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=stream_request_messages,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            yield content