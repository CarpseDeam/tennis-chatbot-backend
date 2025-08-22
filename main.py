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

# Import the routers from the API modules.
from api.routers.chat import router as chat_router
from api.routers.predict import router as predict_router  # <-- ADD THIS LINE

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- FastAPI Application Initialization ---
app = FastAPI(
    title="Tennis AI API",
    version="2.0.0",  # Version 2.0 with ML prediction!
    description="An API combining a quantitative ML model for tennis predictions "
                "with a conversational LLM for user interaction.",
)

# --- Include API Routers ---
app.include_router(chat_router)
app.include_router(predict_router)  # <-- ADD THIS LINE
logger.info("Chat and Prediction API routers included successfully.")


@app.get("/", tags=["Health Check"])
def root() -> Dict[str, str]:
    """
    Root endpoint for basic health checks.
    """
    logger.info("Health check endpoint '/' was accessed.")
    return {"status": "online", "message": "Welcome to the Tennis AI API"}


# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)