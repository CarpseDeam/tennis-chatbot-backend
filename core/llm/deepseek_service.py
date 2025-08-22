# core/llm/deepseek_service.py
"""
Concrete implementation of the LLMService for DeepSeek.
"""
import logging
from typing import List
from openai import AsyncOpenAI
from .base import LLMService
from config import settings
from schemas.chat_schemas import ChatMessage

logger = logging.getLogger(__name__)


class DeepSeekService(LLMService):
    """LLM Service implementation for DeepSeek API (OpenAI compatible)."""

    def __init__(self):
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set in the environment.")

        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model_name = settings.deepseek_model_name
        logger.info(f"DeepSeek service initialized with model: {self.model_name}")

    def _convert_history(self, history: List[ChatMessage]) -> List[dict]:
        messages = [{
            "role": "system",
            "content": "You are a friendly, enthusiastic, and helpful tennis assistant. Answer questions based ONLY on the information provided in the conversation."
        }]
        for msg in history:
            role = "assistant" if msg.role.lower() in ["assistant", "model"] else "user"
            messages.append({"role": role, "content": msg.content})
        return messages

    async def generate_response_async(self, query: str, history: List[ChatMessage]) -> str:
        messages = self._convert_history(history)
        messages.append({"role": "user", "content": query})

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )
        return response.choices[0].message.content