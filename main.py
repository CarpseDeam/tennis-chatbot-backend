# main.py
import logging
import uvicorn
from fastapi import FastAPI
from typing import Dict

# Import all three of our routers
from api.routers.chat import router as chat_router
from api.routers.predict import router as predict_router
from api.routers.orchestrate import router as orchestrate_router # <-- ADD THIS

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
    version="2.1.0", # Version 2.1 with Orchestration!
    description="An API combining a quantitative ML model, a conversational LLM, and an orchestration layer.",
)

# --- Include API Routers ---
app.include_router(chat_router)
app.include_router(predict_router)
app.include_router(orchestrate_router) # <-- ADD THIS
logger.info("Chat, Prediction, and Orchestration API routers included successfully.")


@app.get("/", tags=["Health Check"])
def root() -> Dict[str, str]:
    """Root endpoint for basic health checks."""
    logger.info("Health check endpoint '/' was accessed.")
    return {"status": "online", "message": "Welcome to the Tennis AI API"}


# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

