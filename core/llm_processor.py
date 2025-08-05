# core/llm_processor.py

"""
Orchestrates the entire interaction with the Gemini model. It takes a user query,
manages the tool-calling loop, executes the appropriate tool function
(with fallback logic), and generates the final natural language response.
"""

import logging
import inspect
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

MODEL_NAME = "models/gemini-2.5-flash"

SYSTEM_INSTRUCTION = "You are a helpful and direct tennis assistant. When you have the answer from a tool, respond with only the answer, concisely and directly. Do not mention your tools, the API, or that you performed a web search. For example, instead of 'Based on my search, Player A won', your entire response should be just 'Player A won'."

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=GEMINI_TOOLS,
    system_instruction=SYSTEM_INSTRUCTION,
)
logger.info(f"Generative model '{MODEL_NAME}' initialized with a custom system instruction.")


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

            is_clarification_question = (
                    turn_num == 0
                    and not response.parts[0].function_call
                    and not used_sources
            )

            if is_clarification_question:
                logger.warning("LLM asked for clarification. Forcing a web search to provide context.")
                tool_output = perform_web_search(request.query) # This remains synchronous
                used_sources.append("web_search_client: perform_web_search")
                web_context = tool_output.get('context') or "No information found."
                new_prompt = (
                    f"Context from a web search: {web_context}\n\n"
                    f"Based ONLY on the context above, please answer my original question: '{request.query}'"
                )
                logger.info("Sending new enriched prompt to Gemini after forced web search.")
                response = await chat.send_message_async(new_prompt)

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
                        # --- ASYNC TOOL HANDLING ---
                        if inspect.iscoroutinefunction(tool_function):
                            tool_output = await tool_function(**args)
                        else:
                            tool_output = tool_function(**args)
                        # --- END ASYNC TOOL HANDLING ---

                        module_name = tool_function.__module__.split('.')[-1]
                        source_name = f"{module_name}: {function_name}"
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
                logger.error("Response was identified as a tool call, but no valid function calls were processed.")
                return ChatResponse(response="I tried to use a tool, but something went wrong. Please try again.")

            prompt = tool_responses

        logger.warning(f"Exceeded max tool-calling turns ({max_turns}).")
        return ChatResponse(response="I'm having trouble finding an answer. Please try rephrasing your question.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred in process_chat_request: {e}", exc_info=True)
        return ChatResponse(response="I'm sorry, a critical error occurred and I can't process your request right now.")