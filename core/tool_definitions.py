# core/tool_definitions.py

"""
Defines the tools that the Gemini model can use.
This has been simplified to provide fewer, more powerful tools to the LLM,
improving its decision-making accuracy and speed.
"""

import logging
from typing import Any, Callable, Dict, List

from google.generativeai.protos import FunctionDeclaration, Schema, Tool, Type

# Import the actual functions that the tools will execute
from services.tennis_api_client import (
    find_match_and_get_details,
    get_general_schedule, # Renamed from get_scheduled_events_by_date
    get_h2h_events,
    get_rankings,
    debug_api_search,
)
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)

# --- Tool Definitions for the Gemini API ---

# --- THE NEW, ROBUST SUPER-TOOL for all specific match queries ---
find_match_and_get_details_func = FunctionDeclaration(
    name="find_match_and_get_details",
    description="Use this to find everything about a specific tennis match when player names are mentioned. It can find LIVE scores, upcoming match times, and past results with detailed stats. If no date is given, it will first check for a live match. If no live match is found, it finds past matches and you can ask the user to clarify which one they mean.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The name of one of the players in the match."),
            "player2_name": Schema(type=Type.STRING, description="(Optional) The name of the second player. Providing both is best."),
            "date": Schema(type=Type.STRING, description="(Optional) The date of the match. Can be 'today', 'tomorrow', 'yesterday', or 'YYYY-MM-DD'."),
        },
        required=["player1_name"],
    ),
)

# --- A tool for GENERAL schedules, NOT specific matches ---
get_general_schedule_func = FunctionDeclaration(
    name="get_general_schedule",
    description="Use this for BROAD questions about the day's schedule, like 'Who is playing today?' or 'What matches are on tomorrow?'. DO NOT use this if the user asks about specific players; use 'find_match_and_get_details' for that.",
    parameters=Schema(type=Type.OBJECT, properties={"date": Schema(type=Type.STRING, description="The date to fetch the general schedule for. Can be 'today', 'tomorrow', or a date like '2024-12-25'.")}, required=["date"],),
)

get_h2h_events_func = FunctionDeclaration(
    name="get_h2h_events",
    description="Fetches the career head-to-head (H2H) win/loss record and match history between two players. Use this for questions like 'What is the record between Player A and Player B?'.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The full name of the first tennis player."),
            "player2_name": Schema(type=Type.STRING, description="The full name of the second tennis player."),
        },
        required=["player1_name", "player2_name"],
    ),
)

get_rankings_func = FunctionDeclaration(
    name="get_rankings",
    description="Fetches the official world tennis rankings for either men (ATP) or women (WTA).",
    parameters=Schema(type=Type.OBJECT, properties={"ranking_type": Schema(type=Type.STRING, description="The type of ranking to fetch. Must be either 'atp' or 'wta'.")}, required=["ranking_type"],),
)

perform_web_search_func = FunctionDeclaration(
    name="perform_web_search",
    description="A fallback tool for general knowledge, news, player history, or if other specialized tools fail or do not provide a clear answer.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING, description="The user's original question to search on the web.")}, required=["query"],),
)

debug_api_search_func = FunctionDeclaration(
    name="debug_api_search",
    description="(FOR DEBUGGING) Fetches the raw JSON results from the player search API to see what the API returns for a given player's name.",
    parameters=Schema(type=Type.OBJECT, properties={"player_name": Schema(type=Type.STRING, description="The full name of the player to search for, e.g., 'Carlos Alcaraz'.")}, required=["player_name"],),)


# --- THE NEW SIMPLIFIED AND POWERFUL TOOLSET ---
GEMINI_TOOLS: List[Tool] = [
    Tool(function_declarations=[
        find_match_and_get_details_func,  # The new primary "super-tool"
        get_general_schedule_func,        # For broad schedule questions
        get_h2h_events_func,
        get_rankings_func,
        perform_web_search_func,
        debug_api_search_func,
    ])
]

# The registry mapping tool names to the actual Python functions
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "find_match_and_get_details": find_match_and_get_details,
    "get_general_schedule": get_general_schedule,
    "get_h2h_events": get_h2h_events,
    "get_rankings": get_rankings,
    "perform_web_search": perform_web_search,
    "debug_api_search": debug_api_search,
}