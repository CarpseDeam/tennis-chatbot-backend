# core/llm/gemini_service.py
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration

from .base import LLMService
from config import settings
from schemas.chat_schemas import ChatMessage
from core.tools.web_search import google_search, SEARCH_TOOL_SCHEMA

logger = logging.getLogger(__name__)


class GeminiService(LLMService):
    """LLM Service for Google Gemini, now with tool-calling capabilities."""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in the environment.")

        genai.configure(api_key=settings.google_api_key)

        system_instruction = """You are a bubbly, helpful,and enthusiastic world-class tennis expert. Your primary goal is to answer user questions about tennis.
        To do this, you MUST use the provided `web_search` tool to find the most current and accurate information.
        After getting the search results, synthesize them into a comprehensive and friendly answer."""

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction,
            tools=[FunctionDeclaration(**SEARCH_TOOL_SCHEMA)]
        )
        logger.info("Google Gemini service initialized in TOOL-CALLING mode.")

    def _convert_history(self, history: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Converts internal ChatMessage format to Gemini's format."""
        gemini_history = []
        for msg in history:
            role = "model" if msg.role.lower() in ["assistant", "model"] else "user"
            gemini_history.append({"role": role, "parts": [msg.content]})
        return gemini_history

    async def generate_response_async(self, query: str, history: List[ChatMessage]) -> str:
        """Generates a response, handling the tool-calling loop if necessary."""
        gemini_history = self._convert_history(history)
        chat = self.model.start_chat(history=gemini_history)

        # Send the initial message to the model
        response = await chat.send_message_async(query)

        try:
            # Check if the model's response includes a request to call a function
            function_call = response.candidates[0].content.parts[0].function_call

            if function_call.name == "web_search":
                search_query = function_call.args['query']
                logger.info(f"Gemini requested tool call: web_search(query='{search_query}')")

                # Execute the actual search function
                tool_response_content = await google_search(search_query)

                # Send the tool's result back to the model
                response = await chat.send_message_async(
                    [genai.types.Part(function_response=genai.types.FunctionResponse(
                        name="web_search",
                        response={"result": tool_response_content}
                    ))]
                )
        except (ValueError, AttributeError, IndexError):
            # No function call was made, or the response format was unexpected.
            # The current response is the final text answer.
            pass

        return response.text