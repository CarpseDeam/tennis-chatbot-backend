# core/tool_definitions.py

"""
Defines the tools that the Gemini model can use.
"""

import logging
from typing import Any, Callable, Dict, List

from google.generativeai.protos import FunctionDeclaration, Schema, Tool, Type

# Import the actual functions that the tools will execute
from services.tennis_api_client import (
    find_match_and_get_details,
    get_scheduled_events_by_date,
    get_live_events,
    get_odds_by_date,
    get_event_statistics,
    get_player_performance,
    get_h2h_events,
    get_rankings,
    debug_api_search,
)
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)

# --- Tool Definitions for the Gemini API ---

# --- THE NEW, ROBUST SUPER-TOOL ---
find_match_and_get_details_func = FunctionDeclaration(
    name="find_match_and_get_details",
    description="The absolute best tool for finding all details about a specific match. Use this to find the score, winner, or statistics (like aces) for a match when you know the player(s) and optionally the date. This tool automatically finds the match and gets all available data in one step.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The name of one of the players in the match."),
            "player2_name": Schema(type=Type.STRING, description="(Optional) The name of the second player in the match for a more specific search."),
            "date": Schema(type=Type.STRING, description="The date of the match. Can be 'today', 'tomorrow', 'yesterday', or a date like '2024-12-25'."),
        },
        required=["player1_name", "date"],
    ),
)

get_h2h_events_func = FunctionDeclaration(
    name="get_h2h_events",
    description="Fetches the career head-to-head (H2H) win/loss record between two players. This is for the overall historical record, not for the score of a single recent match.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "player1_name": Schema(type=Type.STRING, description="The full name of the first tennis player."),
            "player2_name": Schema(type=Type.STRING, description="The full name of the second tennis player."),
        },
        required=["player1_name", "player2_name"],
    ),
)

perform_web_search_func = FunctionDeclaration(
    name="perform_web_search",
    description="A fallback tool for general or ambiguous questions, news, player history, or if other specialized tools fail or do not apply.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING, description="The user's original question to search on the web.")}, required=["query"],),
)


get_scheduled_events_by_date_func = FunctionDeclaration(
    name="get_scheduled_events_by_date",
    description="Fetches a general list of all scheduled tennis matches for a specific date. The 'date' parameter can be 'today', 'tomorrow', or a specific date in 'YYYY-MM-DD' format.",
    parameters=Schema(type=Type.OBJECT, properties={"date": Schema(type=Type.STRING, description="The date to fetch events for. Can be 'today', 'tomorrow', or a date like '2024-12-25'.")}, required=["date"],),
)
get_live_events_func = FunctionDeclaration(name="get_live_events", description="Fetches all tennis matches that are currently live. Provides real-time score information and event IDs.",)
get_odds_by_date_func = FunctionDeclaration(name="get_odds_by_date", description="Fetches betting odds for matches on a specific date. The 'date' parameter can be 'today', 'tomorrow', or a specific date in 'YYYY-MM-DD' format.", parameters=Schema(type=Type.OBJECT, properties={"date": Schema(type=Type.STRING, description="The date to fetch odds for. Can be 'today', 'tomorrow', or a date like '2024-12-25'.")}, required=["date"],),)
get_event_statistics_func = FunctionDeclaration(name="get_event_statistics", description="Fetches detailed statistics for a single, specific match using its event ID. This is a low-level tool; prefer using 'find_match_and_get_details' instead.", parameters=Schema(type=Type.OBJECT, properties={"event_id": Schema(type=Type.STRING, description="The unique identifier for the tennis match.")}, required=["event_id"],),)
get_player_performance_func = FunctionDeclaration(name="get_player_performance", description="Fetches the recent match history for a specific player using their player ID. Useful for analyzing a player's recent form.", parameters=Schema(type=Type.OBJECT, properties={"player_id": Schema(type=Type.STRING, description="The unique identifier for the player.")}, required=["player_id"],),)
get_rankings_func = FunctionDeclaration(name="get_rankings", description="Fetches the official world tennis rankings for either men (ATP) or women (WTA).", parameters=Schema(type=Type.OBJECT, properties={"ranking_type": Schema(type=Type.STRING, description="The type of ranking to fetch. Must be either 'atp' or 'wta'.")}, required=["ranking_type"],),)
debug_api_search_func = FunctionDeclaration(name="debug_api_search", description="(FOR DEBUGGING) Fetches the raw JSON results from the player search API to see what the API returns for a given player's name.", parameters=Schema(type=Type.OBJECT, properties={"player_name": Schema(type=Type.STRING, description="The full name of the player to search for, e.g., 'Carlos Alcaraz'.")}, required=["player_name"],),)

GEMINI_TOOLS: List[Tool] = [
    Tool(function_declarations=[
            find_match_and_get_details_func, # The new primary tool
            get_scheduled_events_by_date_func,
            get_live_events_func,
            get_odds_by_date_func,
            get_event_statistics_func,
            get_player_performance_func,
            get_h2h_events_func,
            get_rankings_func,
            perform_web_search_func,
            debug_api_search_func,
    ])
]

TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "find_match_and_get_details": find_match_and_get_details, # The new primary tool
    "get_scheduled_events_by_date": get_scheduled_events_by_date,
    "get_live_events": get_live_events,
    "get_odds_by_date": get_odds_by_date,
    "get_event_statistics": get_event_statistics,
    "get_player_performance": get_player_performance,
    "get_h2h_events": get_h2h_events,
    "get_rankings": get_rankings,
    "perform_web_search": perform_web_search,
    "debug_api_search": debug_api_search,
}