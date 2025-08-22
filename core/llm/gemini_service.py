# core/llm/gemini_service.py
import logging
from typing import List, Dict, Any, AsyncGenerator
import google.generativeai as genai
# --- THIS IMPORT IS THE CORRECT AND ROBUST WAY ---
from google.generativeai import types as genai_types

from .base import LLMService
from config import settings
from schemas.chat_schemas import ChatMessage
from core.tools.web_search import google_search, SEARCH_TOOL_SCHEMA

logger = logging.getLogger(__name__)


class GeminiService(LLMService):
    """LLM Service for Google Gemini, with streaming and tool-calling."""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in the environment.")

        genai.configure(api_key=settings.google_api_key)

        system_instruction = """You are a world-class tennis expert. Your primary goal is to answer user questions about tennis.
        To do this, you MUST use the provided `web_search` tool to find the most current and accurate information.
        After getting the search results, synthesize them into a comprehensive and friendly answer."""

        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction,
            tools=[genai_types.FunctionDeclaration(**SEARCH_TOOL_SCHEMA)]
        )
        logger.info("Google Gemini service initialized in TOOL-CALLING mode.")

    def _convert_history(self, history: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Converts internal ChatMessage format to Gemini's format."""
        gemini_history = []
        for msg in history:
            role = "model" if msg.role.lower() in ["assistant", "model"] else "user"
            gemini_history.append({"role": role, "parts": [msg.content]})
        return gemini_history

    async def generate_response_async(self, query: str, history: List[ChatMessage]) -> AsyncGenerator[str, None]:
        """Generates a streaming response, handling the tool-calling loop."""
        gemini_history = self._convert_history(history)
        chat = self.model.start_chat(history=gemini_history)

        response = await chat.send_message_async(query)

        try:
            function_call = response.candidates[0].content.parts[0].function_call
        except (ValueError, AttributeError, IndexError):
            if response.text:
                yield response.text
            return

        if function_call.name == "web_search":
            search_query = function_call.args['query']
            logger.info(f"Gemini requested tool call: web_search(query='{search_query}')")

            tool_response_content = await google_search(search_query)

            final_response_stream = await chat.send_message_async(
                genai_types.FunctionResponse(name="web_search", response={"result": tool_response_content}),
                stream=True
            )

            async for chunk in final_response_stream:
                if chunk.text:
                    yield chunk.text
        else:
            yield "I'm sorry, I tried to use a tool I don't have access to."