# api/routers/chat.py

"""
Defines the FastAPI router and the specific '/api/chat' POST endpoint.

This module creates a FastAPI APIRouter to handle chat-related routes.
It defines the main POST endpoint that receives user queries, passes them
to the core LLM processor, and returns the generated response. It acts as the
primary interface between the web server and the application's core logic.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from core.llm_processor import process_chat_request
from schemas.chat_schemas import ChatRequest, ChatResponse, ChatMessage
from .. import session_manager

# Set up a logger for this module
logger = logging.getLogger(__name__)

# Create a new router object for chat-related endpoints.
router = APIRouter(
    prefix="/api",
    tags=["Chat"]  # This is the default tag for endpoints in this router
)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Handles an incoming chat request.
    This is the main public endpoint for user interaction.
    It now supports session management to maintain conversation context.
    """
    logger.info(f"Received chat request with query: '{request.query}' for session_id: '{request.session_id}'")

    # If a session ID is provided, use the server-side history.
    # The client-sent history is ignored in this case.
    if request.session_id:
        request.history = session_manager.get_history(request.session_id)
        if request.history:
            logger.info(f"Loaded {len(request.history)} messages from history for session_id: '{request.session_id}'")
    try:
        response = await process_chat_request(request)
        logger.info("Successfully processed chat request.")

        # If a session ID was provided, update the history.
        if request.session_id:
            user_message = ChatMessage(role="user", content=request.query)
            session_manager.update_history(
                session_id=request.session_id,
                user_query=user_message,
                model_response_content=response.response
            )
        return response
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred while processing chat request: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred. Please try again later."
        )