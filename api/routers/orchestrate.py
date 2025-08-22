# api/routers/orchestrate.py
import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from schemas.chat_schemas import ChatRequest, ChatResponse
# Correctly import the streaming function
from core.chat_orchestrator import process_chat_request_stream
from .predict import predict_match as get_prediction

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Orchestration"]
)


@router.post("/predict-and-chat", response_model=ChatResponse)
async def predict_and_chat_endpoint(request: Dict[str, Any]) -> ChatResponse:
    """
    Orchestrates a full predict-then-chat flow with a single API call.
    This endpoint now correctly handles the internal streaming chat service.
    """
    try:
        user_query_text = request.get("user_query")
        live_data = request.get("live_data")

        if not user_query_text or not live_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must contain 'user_query' and 'live_data' keys."
            )

        logger.info("Orchestrator: Calling internal prediction service.")
        prediction_result = await get_prediction(live_data)

        system_prompt = (
            f"The user is asking: '{user_query_text}'.\n"
            f"Our internal machine learning model has analyzed the data and produced the following result:\n"
            f"- Predicted Winner: {prediction_result.predicted_winner}\n"
            f"- Player 1's Win Probability: {prediction_result.p1_win_probability:.2%}\n\n"
            f"Based on this data, please provide a friendly, conversational answer to the user."
        )
        logger.info(f"Orchestrator: Constructed detailed prompt for LLM.")

        # Create a ChatRequest for the internal streaming service
        chat_request = ChatRequest(query=system_prompt)

        # --- Consume the Stream Internally ---
        # We will collect all the chunks from the stream and join them together.
        response_chunks = []
        async for chunk in process_chat_request_stream(chat_request):
            response_chunks.append(chunk)

        final_response_text = "".join(response_chunks)
        # ------------------------------------

        logger.info("Orchestrator: Successfully received and assembled final response.")
        return ChatResponse(response=final_response_text)

    except HTTPException:
        raise
    except Exception as e:
        logger.critical(f"An error occurred in the orchestration endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred during orchestration."
        )