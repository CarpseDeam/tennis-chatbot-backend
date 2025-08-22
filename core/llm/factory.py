# core/llm/factory.py
"""
Factory module to instantiate the correct LLM service based on settings.
"""
import logging
from config import settings
from .base import LLMService
from .gemini_service import GeminiService
from .deepseek_service import DeepSeekService

logger = logging.getLogger(__name__)

# A single, cached instance of the service
_llm_service_instance: LLMService | None = None

def get_llm_service() -> LLMService:
    """
    Factory function that returns the configured LLM service instance.
    It creates the instance on the first call and returns the cached
    instance on subsequent calls.
    """
    global _llm_service_instance
    if _llm_service_instance is None:
        provider = settings.llm_provider.lower()
        logger.info(f"Creating LLM service for provider: '{provider}'")
        if provider == 'google':
            _llm_service_instance = GeminiService()
        elif provider == 'deepseek':
            _llm_service_instance = DeepSeekService()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    return _llm_service_instance