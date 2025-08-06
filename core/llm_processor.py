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

# --- DYNAMIC AND ROBUST SYSTEM PROMPT ---
# This prompt gives the model clearer instructions on how to act smart.
SYSTEM_INSTRUCTION = """You are a friendly, enthusiastic, and helpful tennis assistant. Your tone should be that of a passionate tennis expert who loves sharing stats and fun facts.

Your primary goal is to provide direct, accurate answers. Follow these rules:
1.  **NEVER mention your tools.** Do not say "I used a tool" or "I performed a search." Act like you know the information yourself. This is our little secret.
2.  **Prioritize Clarity.** If a tool gives you a list of matches (clarification options), present these options clearly to the user so they can choose.
3.  **Be a Smart Problem-Solver.** If a primary tool fails, you will receive an error message and supplemental information from a web search. Use the web search information to answer the user's original question to the best of your ability.
"""

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=GEMINI_TOOLS,
    system_instruction=SYSTEM_INSTRUCTION,
)
logger.info(f"Generative model '{MODEL_NAME}' initialized with a new DYNAMIC and ROBUST persona!")


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
                tool_output = None
                logger.info(f"Attempting to execute tool: {function_name} with args: {args}")

                if function_name not in TOOL_REGISTRY:
                    logger.error(f"LLM requested an unknown tool: '{function_name}'")
                    tool_output = {"error": f"Tool '{function_name}' not found."}
                else:
                    tool_function = TOOL_REGISTRY[function_name]
                    try:
                        if inspect.iscoroutinefunction(tool_function):
                            tool_output = await tool_function(**args)
                        else:
                            tool_output = tool_function(**args)

                        module_name = tool_function.__module__.split('.')[-1]
                        source_name = f"{module_name}: {function_name}"
                        if source_name not in used_sources:
                            used_sources.append(source_name)

                        # --- ROBUSTNESS: SMART FALLBACK ON TOOL FAILURE ---
                        is_primary_tool_failure = "error" in tool_output and function_name != "perform_web_search"
                        if is_primary_tool_failure:
                            logger.warning(f"Primary tool '{function_name}' failed. Triggering web search fallback.")
                            # Use the original user query for the web search
                            web_search_results = await perform_web_search(request.query)
                            used_sources.append("web_search_client: perform_web_search")

                            # Create a rich context for the LLM
                            fallback_context = {
                                "original_tool_error": tool_output,
                                "web_search_context": web_search_results.get("context", "No information found from web search.")
                            }
                            tool_output = fallback_context
                            logger.info("Created fallback context with web search data for the LLM.")

                    except Exception as e:
                        logger.error(f"Critical error executing tool '{function_name}': {e}", exc_info=True)
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