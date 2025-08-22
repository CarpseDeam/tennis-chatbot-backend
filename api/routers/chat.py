# api/routers/chat.py
import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from core.chat_orchestrator import process_chat_request_stream
from schemas.chat_schemas import ChatRequest
from .. import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Chat"]
)


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Handles an incoming chat request and returns a real-time streaming response.

    This endpoint is optimized for perceived performance by streaming the LLM
    response as it's generated. It retrieves existing session history for context.
    Note: Persisting the full streamed conversation back to Redis is a separate
    concern that can be implemented in a future version if required.
    """
    logger.info(f"Received streaming chat request for session_id: '{request.session_id}'")

    if request.session_id:
        request.history = session_manager.get_history(request.session_id)

    try:
        return StreamingResponse(
            process_chat_request_stream(request),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred in the chat endpoint: {e}",
            exc_info=True
        )
        # This error is for issues that occur before the stream begins.
        # Errors during the stream are handled within the generator.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred before the stream could start."
        )