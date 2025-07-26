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
from schemas.chat_schemas import ChatRequest, ChatResponse

# Set up a logger for this module
logger = logging.getLogger(__name__)

# Create a new router object for chat-related endpoints.
# The prefix ensures all routes in this file start with '/api'.
# The tags are used for grouping in the auto-generated API docs.
router = APIRouter(
    prefix="/api",
    tags=["Chat"]
)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Handles an incoming chat request.

    This endpoint receives a user's query and conversation history,
    processes it using the backend LLM processor, and returns a structured
    response containing the model's answer and any sources used.

    Args:
        request (ChatRequest): The incoming request body, validated against
            the ChatRequest Pydantic model.

    Returns:
        ChatResponse: The response from the chat model, conforming to the
            ChatResponse Pydantic model.

    Raises:
        HTTPException: An exception with status code 500 if an unexpected
            error occurs during processing.
    """
    logger.info(f"Received chat request with query: '{request.query}'")
    try:
        # Delegate the core logic to the llm_processor. This function handles
        # the entire interaction with the Gemini model, including tool calls.
        response = await process_chat_request(request)
        logger.info("Successfully processed chat request.")
        return response
    except Exception as e:
        # Log the full exception details for debugging purposes.
        # The `exc_info=True` argument includes the stack trace in the log.
        logger.critical(
            f"An unexpected error occurred while processing chat request: {e}",
            exc_info=True
        )
        # Return a generic 500 error to the client to avoid leaking
        # sensitive implementation details.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred. Please try again later."
        )