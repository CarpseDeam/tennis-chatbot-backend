# api/routers/orchestrate.py

"""
Defines the FastAPI router for high-level orchestration endpoints.

These endpoints combine multiple internal services to provide a single,
streamlined response for the client application.
"""
import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from schemas.chat_schemas import ChatRequest, ChatResponse
from core.chat_orchestrator import process_chat_request

# We will import the internal LOGIC from our other routers, not the routers themselves.
from .predict import predict_match as get_prediction
from ..session_manager import update_history, get_history, set_initial_context

logger = logging.getLogger(__name__)

# --- Router Setup ---
router = APIRouter(
    prefix="/api",
    tags=["Orchestration"]
)


# --- The "Predict and Chat" Endpoint ---
@router.post("/predict-and-chat", response_model=ChatResponse)
async def predict_and_chat_endpoint(request: Dict[str, Any]):
    """
    Orchestrates a full predict-then-chat flow with a single API call.

    This endpoint:
    1. Accepts the huge raw JSON for prediction.
    2. Calls the internal prediction logic to get a numerical result.
    3. Constructs a new, detailed prompt for the LLM.
    4. Calls the internal chat logic to get a conversational explanation.
    5. Returns the final text response to the client.
    """
    try:
        # We assume the incoming request has the huge JSON and a 'user_query' field.
        # Example: {"user_query": "who will win?", "live_data": { ... the huge json ... }}
        user_query_text = request.get("user_query")
        live_data = request.get("live_data")

        if not user_query_text or not live_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must contain 'user_query' and 'live_data' keys."
            )

        # --- Step 1: Call the Prediction Logic ---
        logger.info("Orchestrator: Calling internal prediction service.")
        prediction_result = await get_prediction(live_data)

        p1_prob = prediction_result.p1_win_probability
        winner = prediction_result.predicted_winner

        # --- Step 2: Construct the Detailed Prompt for the LLM ---
        # This is where we inject the quantitative result into a qualitative prompt.
        system_prompt = (
            f"The user is asking: '{user_query_text}'.\n"
            f"Our internal machine learning model has analyzed the data and produced the following result:\n"
            f"- Predicted Winner: {winner}\n"
            f"- Player 1's Win Probability: {p1_prob:.2%}\n\n"
            f"Based on this data, please provide a friendly, conversational answer to the user."
        )
        logger.info(f"Orchestrator: Constructed detailed prompt for LLM: '{system_prompt}'")

        # --- Step 3: Call the Chat Logic ---
        # We create a new ChatRequest on the fly to pass to our existing chat orchestrator
        chat_request = ChatRequest(query=system_prompt)
        final_response = await process_chat_request(chat_request)

        logger.info("Orchestrator: Successfully received final response from chat service.")
        return final_response

    except HTTPException:
        # Re-raise HTTP exceptions from downstream services
        raise
    except Exception as e:
        logger.critical(f"An error occurred in the orchestration endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred during orchestration."
        )