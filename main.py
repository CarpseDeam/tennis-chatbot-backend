# main.py

"""
The main entry point of the application.

This module initializes the FastAPI application, configures basic logging,
includes the necessary API routers from other parts of the application,
and defines the main execution block to start the Uvicorn server.
Its primary role is to assemble and launch all the application components.
"""

import logging
import uvicorn
from fastapi import FastAPI
from typing import Dict

# Import the router from the chat API module.
# This router contains all the endpoints defined in api/routers/chat.py.
from api.routers.chat import router as chat_router

# --- Logging Configuration ---
# Configure the root logger to output messages at the INFO level and above.
# This basic configuration is set up at the application's entry point to ensure
# all subsequent logging activities are captured.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set up a logger for this specific module.
logger = logging.getLogger(__name__)


# --- FastAPI Application Initialization ---
# Create the main FastAPI application instance.
# Metadata like title, version, and description are provided here, which will be
# used in the automatically generated API documentation (e.g., at /docs).
app = FastAPI(
    title="Tennis AI Chatbot API",
    version="1.0.0",
    description="An AI-powered chatbot that uses Google Gemini with tool-calling "
                "to answer questions about tennis by integrating with a live Tennis API.",
)

# --- Include API Routers ---
# Include the chat router in the main FastAPI application.
# All routes defined in the chat_router (e.g., /api/chat) will now be
# part of the main application.
app.include_router(chat_router)
logger.info("Chat API router included successfully.")


@app.get("/", tags=["Health Check"])
def root() -> Dict[str, str]:
    """
    Root endpoint for basic health checks.

    This endpoint can be used by monitoring services or load balancers to verify
    that the application is running and responsive.

    Returns:
        Dict[str, str]: A dictionary with a status message indicating the API is online.
    """
    logger.info("Health check endpoint '/' was accessed.")
    return {"status": "online", "message": "Welcome to the Tennis AI Chatbot API"}


# --- Main Execution Block ---
# This block runs when the script is executed directly (e.g., `python main.py`).
# It starts the Uvicorn server, which is a high-performance ASGI server, to serve
# the FastAPI application.
if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    # The `reload=True` argument enables auto-reloading of the server when code
    # changes are detected, which is useful for development.
    # The host '0.0.0.0' makes the server accessible on the network.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)