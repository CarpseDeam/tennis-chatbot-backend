# api/routers/chat.py

"""
Defines the FastAPI router and the specific '/api/chat' POST endpoint.

This module creates a FastAPI APIRouter to handle chat-related routes.
It defines the main POST endpoint that receives user queries, passes them
to the core LLM processor, and returns the generated response. It acts as the
primary interface between the web server and the application's core logic.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Any, Dict

from core.llm_processor import process_chat_request
from schemas.chat_schemas import ChatRequest, ChatResponse
from services.web_search_client import perform_web_search
# Import our security dependency
from api.dependencies import verify_admin_key

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
    """
    logger.info(f"Received chat request with query: '{request.query}'")
    try:
        response = await process_chat_request(request)
        logger.info("Successfully processed chat request.")
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


@router.get(
    "/debug/search",
    # This explicit tag separates it from the "Chat" endpoints
    tags=["Debugging"],
    response_model=Dict[str, Any],
    # This line locks the endpoint
    dependencies=[Depends(verify_admin_key)]
)
async def debug_search(q: str):
    """
    An ADMIN-ONLY endpoint to directly test the Google Search tool.
    Requires a valid `X-Admin-API-Key` header to be present in the request.
    """
    logger.info(f"--- ADMIN DEBUG SEARCH --- Received search request for query: '{q}'")
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' cannot be empty.")

    results = await perform_web_search(q)
    return results