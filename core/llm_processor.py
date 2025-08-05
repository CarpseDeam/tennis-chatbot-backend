# core/llm_processor.py

"""
Orchestrates the entire interaction with the Gemini model. It takes a user query,
manages the tool-calling loop, executes the appropriate tool function
(with fallback logic), and generates the final natural language response.
"""

import logging
from typing import List, Dict, Any

import google.generativeai as genai

from config import settings
from schemas.chat_schemas import ChatRequest, ChatResponse, ChatMessage
from core.tool_definitions import GEMINI_TOOLS, TOOL_REGISTRY
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)

# --- Model Configuration ---
try:
    genai.configure(api_key=settings.google_api_key)
    logger.info("Google Generative AI client configured successfully.")
except Exception as e:
    logger.critical(f"FATAL: Failed to configure Google Generative AI client: {e}")
    raise

MODEL_NAME = "models/gemini-1.5-flash-latest"
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=GEMINI_TOOLS,
)
logger.info(f"Generative model '{MODEL_NAME}' initialized.")


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
    """
    try:
        history = []
        if request.history:
            history = _convert_history_to_gemini_format(request.history)

        chat = model.start_chat(history=history)
        prompt: Any = request.query
        used_sources: List[str] = []
        max_turns = 5

        for turn_num in range(max_turns):
            logger.info(f"Turn {turn_num + 1}: Sending prompt to Gemini. Prompt type: {type(prompt).__name__}")
            response = await chat.send_message_async(prompt)

            # --- NEW SAFETY NET LOGIC ---
            # Check if the model is asking a question without using a tool on the first turn
            is_clarification_question = (
                    turn_num == 0
                    and not response.parts[0].function_call
                    and not used_sources
            )

            if is_clarification_question:
                logger.warning("LLM asked for clarification instead of using a tool. Forcing a web search.")

                # Manually perform a web search with the original query
                tool_output = perform_web_search(request.query)
                source_name = "web_search_client: perform_web_search"
                if source_name not in used_sources:
                    used_sources.append(source_name)

                logger.info(f"Forced web search returned: {tool_output}")

                # Create the tool response part to send back to the LLM
                prompt = [genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name="perform_web_search",
                        response=tool_output
                    )
                )]
                # Skip to the next turn to send this new info to the LLM
                continue
            # --- END OF SAFETY NET LOGIC ---

            try:
                final_text = response.text
                logger.info(f"LLM provided a final text response on turn {turn_num + 1}. Exiting loop.")
                return ChatResponse(
                    response=final_text,
                    sources=used_sources if used_sources else None,
                )
            except ValueError:
                logger.info(f"LLM response on turn {turn_num + 1} contains a function call, proceeding to execute.")
                pass

            tool_responses = []
            for part in response.parts:
                if not part.function_call:
                    continue

                call = part.function_call
                function_name = call.name
                args = dict(call.args)
                logger.info(f"Attempting to execute tool: {function_name} with args: {args}")

                if function_name not in TOOL_REGISTRY:
                    logger.error(f"LLM requested an unknown tool: '{function_name}'")
                    tool_output = {"error": f"Tool '{function_name}' not found."}
                else:
                    tool_function = TOOL_REGISTRY[function_name]
                    try:
                        tool_output = tool_function(**args)
                        module_name = tool_function.__module__.split('.')[-1]
                        source_name = f"{module_name}: {function_name}"

                        if isinstance(tool_output, dict) and tool_output.get("source") == "Self-Hosted Web Scraper":
                            source_name = "web_search_client: perform_web_search"

                        if source_name not in used_sources:
                            used_sources.append(source_name)

                    except Exception as e:
                        logger.error(f"Error executing tool '{function_name}': {e}", exc_info=True)
                        tool_output = {"error": f"Execution failed for tool '{function_name}': {str(e)}"}

                logger.info(f"Tool '{function_name}' returned: {tool_output}")

                tool_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response=tool_output
                        )
                    )
                )

            if not tool_responses:
                logger.error("Response was identified as a tool call, but no function calls were processed or valid.")
                return ChatResponse(response="I tried to use a tool, but something went wrong. Please try again.")

            prompt = tool_responses

        logger.warning(f"Exceeded max tool-calling turns ({max_turns}).")
        return ChatResponse(
            response="I'm having trouble using my tools to find an answer. Please try rephrasing your question.",
            sources=used_sources if used_sources else None,
        )
    except Exception as e:
        logger.critical(f"An unhandled exception occurred in process_chat_request: {e}", exc_info=True)
        return ChatResponse(response="I'm sorry, a critical error occurred and I can't process your request right now.")