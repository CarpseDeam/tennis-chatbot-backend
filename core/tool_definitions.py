# core/tool_definitions.py
"""
Defines the tools that the Gemini model can use.
This file points to the high-level tool functions in `services.tennis_tools`
which orchestrate the logic from the `services.tennis_logic` package.
"""
import logging
from typing import Any, Callable, Dict, List

from google.generativeai.protos import FunctionDeclaration, Schema, Tool, Type

# --- Import from our NEW, CLEAN, REFACTORED toolbox ---
from services.tennis_tools import (
    find_match_and_get_details,
    get_general_schedule,
    get_h2h_events,
    get_rankings,
    get_odds_by_date,
    get_player_recent_matches,
    debug_api_search,
)
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)

# --- Tool Function Declarations ---

find_match_and_get_details_func = FunctionDeclaration(
    name="find_match_and_get_details",
    description="Use to find everything about a specific match when player names are mentioned. It can find LIVE scores, upcoming schedules, and past results with detailed stats.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The name of one player."),
            "player2_name": Schema(type=Type.STRING, description="(Optional) The name of the second player."),
            "date": Schema(type=Type.STRING, description="(Optional) The match date ('today', 'tomorrow', 'YYYY-MM-DD')."),
        },
        required=["player1_name"],
    ),
)

get_player_recent_matches_func = FunctionDeclaration(
    name="get_player_recent_matches",
    description="Fetches recent match history for a single player. Use for questions like 'What are Alcaraz's recent results?' or 'Show me Sinner's last few matches.'",
    parameters=Schema(type=Type.OBJECT, properties={"player_name": Schema(type=Type.STRING, description="The full name of the player.")}, required=["player_name"]),
)

get_h2h_events_func = FunctionDeclaration(
    name="get_h2h_events",
    description="Gets the head-to-head career record between two players. Use for questions like 'What is the record between Player A and Player B?'.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The full name of the first player."),
            "player2_name": Schema(type=Type.STRING, description="The full name of the second player."),
        },
        required=["player1_name", "player2_name"],
    ),
)

get_general_schedule_func = FunctionDeclaration(
    name="get_general_schedule",
    description="Use for BROAD questions about a day's schedule, like 'Who is playing today?' or 'What matches are on tomorrow?'. DO NOT use for specific players.",
    parameters=Schema(type=Type.OBJECT, properties={"date": Schema(type=Type.STRING, description="The date ('today', 'tomorrow', 'YYYY-MM-DD').")}, required=["date"]),
)

get_odds_by_date_func = FunctionDeclaration(
    name="get_odds_by_date",
    description="Fetches betting odds for matches on a specific date. Use for questions like 'What are the betting odds for today?'",
    parameters=Schema(type=Type.OBJECT, properties={"date": Schema(type=Type.STRING, description="The date ('today', 'tomorrow', 'YYYY-MM-DD').")}, required=["date"]),
)

get_rankings_func = FunctionDeclaration(
    name="get_rankings",
    description="Gets the official world tennis rankings for men (ATP) or women (WTA).",
    parameters=Schema(type=Type.OBJECT, properties={"ranking_type": Schema(type=Type.STRING, description="Must be 'atp' or 'wta'.")}, required=["ranking_type"]),
)

perform_web_search_func = FunctionDeclaration(
    name="perform_web_search",
    description="A fallback tool for general knowledge, news, or if other specialized tools fail or do not provide a clear answer.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING, description="The user's original question.")}, required=["query"]),
)

debug_api_search_func = FunctionDeclaration(
    name="debug_api_search",
    description="(FOR DEBUGGING) Fetches raw API results for a player's name.",
    parameters=Schema(type=Type.OBJECT, properties={"player_name": Schema(type=Type.STRING, description="The player's name.")}, required=["player_name"]),
)

# --- Final, Assembled Toolset for the LLM ---
GEMINI_TOOLS: List[Tool] = [
    Tool(function_declarations=[
        find_match_and_get_details_func,
        get_player_recent_matches_func,
        get_h2h_events_func,
        get_general_schedule_func,
        get_odds_by_date_func,
        get_rankings_func,
        perform_web_search_func,
        debug_api_search_func,
    ])
]

# --- Final, Assembled Registry for the Backend ---
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "find_match_and_get_details": find_match_and_get_details,
    "get_player_recent_matches": get_player_recent_matches,
    "get_h2h_events": get_h2h_events,
    "get_general_schedule": get_general_schedule,
    "get_odds_by_date": get_odds_by_date,
    "get_rankings": get_rankings,
    "perform_web_search": perform_web_search,
    "debug_api_search": debug_api_search,
}