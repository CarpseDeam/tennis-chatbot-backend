# core/chat_orchestrator.py
import logging
from typing import AsyncGenerator
from schemas.chat_schemas import ChatRequest
from core.llm.factory import get_llm_service

logger = logging.getLogger(__name__)


async def process_chat_request_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Processes a user's chat request using the configured LLM provider and yields a stream.
    """
    try:
        llm_service = get_llm_service()
        logger.info("Forwarding chat request to the configured LLM service for streaming.")

        async for chunk in llm_service.generate_response_async(
                query=request.query,
                history=request.history or []
        ):
            yield chunk

    except Exception as e:
        logger.critical(f"An unhandled exception occurred in stream processing: {e}", exc_info=True)
        yield "I'm sorry, a critical error occurred and I can't process your request right now."