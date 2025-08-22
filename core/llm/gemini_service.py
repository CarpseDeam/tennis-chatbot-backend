# core/llm/gemini_service.py
"""
Concrete implementation of the LLMService for Google Gemini.
"""
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from .base import LLMService
from config import settings
from schemas.chat_schemas import ChatMessage

logger = logging.getLogger(__name__)


class GeminiService(LLMService):
    """LLM Service implementation for Google Gemini."""

    def __init__(self):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in the environment.")

        genai.configure(api_key=settings.google_api_key)

        system_instruction = """You are a friendly, enthusiastic, and helpful tennis assistant. Your tone should be that of a passionate tennis expert.
Your primary goal is to answer questions based ONLY on the information provided in our conversation history. Do not use any external knowledge. If the answer isn't in the history, say so."""

        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction,
        )
        logger.info("Google Gemini service initialized.")

    def _convert_history(self, history: List[ChatMessage]) -> List[Dict[str, Any]]:
        gemini_history = []
        for msg in history:
            role = "model" if msg.role.lower() in ["assistant", "model"] else "user"
            gemini_history.append({"role": role, "parts": [msg.content]})
        return gemini_history

    async def generate_response_async(self, query: str, history: List[ChatMessage]) -> str:
        gemini_history = self._convert_history(history)
        chat = self.model.start_chat(history=gemini_history)
        response = await chat.send_message_async(query)
        return response.text