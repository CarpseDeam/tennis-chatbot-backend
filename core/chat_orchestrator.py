# core/chat_orchestrator.py

"""
Orchestrates the chat process by getting the configured LLM service
from the factory and passing the request to it.
"""

import logging
from schemas.chat_schemas import ChatRequest, ChatResponse
from core.llm.factory import get_llm_service

logger = logging.getLogger(__name__)


async def process_chat_request(request: ChatRequest) -> ChatResponse:
    """
    Processes a user's chat request using the configured LLM provider.
    """
    try:
        # Get the singleton instance of our configured LLM service
        llm_service = get_llm_service()

        logger.info("Forwarding chat request to the configured LLM service.")
        response_text = await llm_service.generate_response_async(
            query=request.query,
            history=request.history or []
        )
        logger.info("Successfully received response from the LLM service.")

        return ChatResponse(response=response_text)

    except Exception as e:
        logger.critical(f"An unhandled exception occurred in process_chat_request: {e}", exc_info=True)
        return ChatResponse(response="I'm sorry, a critical error occurred and I can't process your request right now.")