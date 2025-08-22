# core/chat_orchestrator.py
import logging
from typing import AsyncGenerator

# Import session_manager to save the conversation history
from api import session_manager
from core.llm.factory import get_llm_service
# Import ChatMessage to construct the user's message object for saving
from schemas.chat_schemas import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)


async def process_chat_request_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Processes a user's chat request, yields a stream for the client,
    and saves the full conversation turn to the Redis session history.
    """
    try:
        llm_service = get_llm_service()
        logger.info("Forwarding chat request to the configured LLM service for streaming.")

        # We need to collect the response chunks to save the full message later
        response_chunks = []
        user_message = ChatMessage(role="user", content=request.query)

        # Stream the response to the client chunk by chunk
        async for chunk in llm_service.generate_response_async(
            query=request.query, history=request.history or []
        ):
            response_chunks.append(chunk)
            yield chunk

        # After the stream is complete, assemble the full response
        final_response_content = "".join(response_chunks)

        # If a session_id was provided, save the user query and the full model response
        if request.session_id:
            logger.info(f"Saving full conversation turn to Redis for session_id: '{request.session_id}'")
            session_manager.update_history(
                session_id=request.session_id,
                user_query=user_message,
                model_response_content=final_response_content,
            )

    except Exception as e:
        logger.critical(f"An unhandled exception occurred in stream processing: {e}", exc_info=True)
        yield "I'm sorry, a critical error occurred and I can't process your request right now."