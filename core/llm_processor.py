# core/llm_processor.py

"""
Orchestrates the interaction with the Gemini model. It takes a user query
and conversation history, and generates a natural language response based
solely on the provided context.
"""

import logging
from typing import List, Dict, Any

import google.generativeai as genai

from config import settings
from schemas.chat_schemas import ChatRequest, ChatResponse, ChatMessage

logger = logging.getLogger(__name__)

# --- Model Configuration ---
try:
    genai.configure(api_key=settings.google_api_key)
    logger.info("Google Generative AI client configured successfully.")
except Exception as e:
    logger.critical(f"FATAL: Failed to configure Google Generative AI client: {e}")
    raise

MODEL_NAME = "models/gemini-2.5-flash"

# --- NEW, FOCUSED SYSTEM PROMPT ---
# This prompt instructs the model to ONLY use the conversation history.
SYSTEM_INSTRUCTION = """You are a friendly, enthusiastic, and helpful tennis assistant. Your tone should be that of a passionate tennis expert.

Your primary goal is to answer questions based **ONLY** on the information provided in our conversation history. Follow these rules strictly:
1.  **Stick to the Provided Context.** Your knowledge is limited to the text and data I have given you in previous messages. Do not use any external knowledge.
2.  **Do Not Make Things Up.** If the answer to a question cannot be found in our conversation history, you MUST say "I'm sorry, but I don't have that information in our current conversation." Do not guess or hallucinate an answer.
3.  **Be Conversational.** Use the context to answer questions naturally. For example, if the user asks "what did you just show me?", you should summarize the data chunks you were just given.
"""

# We initialize the model WITHOUT any tools. This is the key change.
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    # No 'tools' parameter means no tool-calling!
    system_instruction=SYSTEM_INSTRUCTION,
)
logger.info(f"Generative model '{MODEL_NAME}' initialized in CONTEXT-ONLY mode. Tool-calling is disabled.")


def _convert_history_to_gemini_format(
        history: List[ChatMessage],
) -> List[Dict[str, Any]]:
    """
    Converts a list of Pydantic ChatMessage objects to Gemini's history format.
    """
    gemini_history = []
    for msg in history:
        role = "model" if msg.role.lower() in ["assistant", "model"] else "user"
        gemini_history.append({"role": role, "parts": [msg.content]})
    return gemini_history


async def process_chat_request(request: ChatRequest) -> ChatResponse:
    """
    Processes a user's chat request by orchestrating with the Gemini model.
    This version is simplified to be purely conversational without tool-calling.
    """
    try:
        history = []
        if request.history:
            history = _convert_history_to_gemini_format(request.history)

        chat = model.start_chat(history=history)
        logger.info("Sending prompt to Gemini for a direct text response.")
        response = await chat.send_message_async(request.query)

        final_text = response.text
        logger.info("Successfully received a text response from the LLM.")

        return ChatResponse(response=final_text)

    except Exception as e:
        logger.critical(f"An unhandled exception occurred in process_chat_request: {e}", exc_info=True)
        return ChatResponse(response="I'm sorry, a critical error occurred and I can't process your request right now.")