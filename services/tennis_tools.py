# services/tennis_tools.py
"""
This is the primary module for defining high-level tool functions that the
LLM can call. It acts as a manager, coordinating calls to the specialist
modules in the `tennis_logic` sub-package to fetch and process data.
"""
import logging
import datetime
import urllib.parse
import asyncio
from typing import Any, Dict, Optional, List

# Import our specialist modules
from services.tennis_logic import api_client, data_parser, player_finder
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)


async def _find_and_process_specific_match(events: List[Dict], p1_name: str, p2_name: Optional[str]) -> Optional[Dict]:
    """Internal helper to find a match in a list and enrich it with stats."""
    target_event = None
    p1_lower = p1_name.lower()
    p2_lower = p2_name.lower() if p2_name else None

    for event in events:
        home_player = event.get("home_player", "").lower()
        away_player = event.get("away_player", "").lower()
        p1_in_match = p1_lower in home_player or p1_lower in away_player
        p2_in_match = not p2_lower or (p2_lower in home_player or p2_lower in away_player)
        if p1_in_match and p2_in_match:
            target_event = event
            break

    if not target_event or not target_event.get("event_id"):
        return None

    logger.info(f"Found target event {target_event['event_id']}. Fetching detailed stats.")
    stats_data = await api_client.make_api_request(f"api/tennis/event/{target_event['event_id']}/statistics")

    target_event.update(stats_data)
    simplified_data = data_parser.simplify_full_match_details(target_event)

    return {
        "summary": "Successfully found and processed match details.",
        "match_details": simplified_data
    }


async def find_match_and_get_details(player1_name: str, player2_name: Optional[str] = None,
                                     date: Optional[str] = None) -> Dict[str, Any]:
    """The 'super-tool' for finding all details about a specific match."""
    logger.info(f"Tool 'find_match_and_get_details' called for P1='{player1_name}', P2='{player2_name}', Date='{date}'")
    search_desc = f"'{player1_name}'" + (f" vs '{player2_name}'" if player2_name else "")

    if date:
        logger.info(f"Date provided. Searching schedule for {date}.")
        daily_events_data = await get_general_schedule(date)
        if "error" in daily_events_data: return daily_events_data

        match_details = await _find_and_process_specific_match(daily_events_data.get("events_preview", []),
                                                               player1_name, player2_name)
        return match_details or {"summary": f"I looked for a match with {search_desc} on {date} but couldn't find one."}

    logger.info("No date provided. Checking for LIVE matches.")
    live_events_raw = await api_client.make_api_request("api/tennis/events/live")
    live_events_parsed = data_parser.parse_event_list(live_events_raw)

    if live_events_parsed.get("events_preview"):
        live_match_details = await _find_and_process_specific_match(live_events_parsed["events_preview"], player1_name,
                                                                    player2_name)
        if live_match_details:
            logger.info("Found LIVE match. Returning immediately.")
            return live_match_details

    logger.info("No live match found. Looking up H2H for clarification.")
    if not player2_name:
        return {"summary": "To find a past match without a date, please provide two player names."}

    h2h_data = await get_h2h_events(player1_name, player2_name)
    if h2h_data.get("recent_matches"):
        return {
            "summary": f"I couldn't find a live match, but I found several recent matches for {player1_name} and {player2_name}. Please ask the user to clarify.",
            "clarification_options": h2h_data["recent_matches"]
        }
    return h2h_data


async def get_h2h_events(player1_name: str, player2_name: str) -> Dict[str, Any]:
    """Gets the head-to-head history for two players."""
    logger.info(f"Tool 'get_h2h_events' called for '{player1_name}' vs '{player2_name}'")

    p1_id, p2_id = await asyncio.gather(
        player_finder.find_player_id_by_name(player1_name),
        player_finder.find_player_id_by_name(player2_name)
    )

    if not all([p1_id, p2_id]):
        failed = player1_name if not p1_id else player2_name
        return {
            "summary": f"I had trouble finding a player named '{failed}'. Could you try their full name or check the spelling?"}

    raw_data = await api_client.make_api_request(f"api/tennis/player/{p1_id}/h2h/{p2_id}")
    if "error" in raw_data or not raw_data.get("events"):
        return {"summary": f"I couldn't find any head-to-head match history between {player1_name} and {player2_name}."}

    return data_parser.parse_h2h_data(raw_data, p1_id, p2_id, player1_name, player2_name)


async def get_general_schedule(date: str) -> Dict[str, Any]:
    """Gets a list of all scheduled tennis matches for a specific date."""
    logger.info(f"Tool 'get_general_schedule' called for date: {date}")
    try:
        date_map = {'today': 0, 'tomorrow': 1, 'yesterday': -1}
        delta = date_map.get(date.lower())
        target_date = datetime.date.today() + datetime.timedelta(
            days=delta) if delta is not None else datetime.datetime.strptime(date, "%Y-%m-%d").date()
        api_date_str = target_date.strftime("%d/%m/%Y")

        raw_data = await api_client.make_api_request(f"api/tennis/events/{api_date_str}")
        return data_parser.parse_event_list(raw_data)
    except ValueError:
        return {"error": "Invalid date format. Please use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


# --- SPRINT FEATURE 1 ---
async def get_odds_by_date(date: str) -> Dict[str, Any]:
    """Gets betting odds for all matches on a specific date."""
    logger.info(f"Tool 'get_odds_by_date' called for date: {date}")
    try:
        date_map = {'today': 0, 'tomorrow': 1, 'yesterday': -1}
        delta = date_map.get(date.lower())
        target_date = datetime.date.today() + datetime.timedelta(
            days=delta) if delta is not None else datetime.datetime.strptime(date, "%Y-%m-%d").date()
        api_date_str = target_date.strftime("%d/%m/%Y")

        raw_data = await api_client.make_api_request(f"api/tennis/events/odds/{api_date_str}")
        return data_parser.parse_event_list(
            raw_data)  # Odds endpoint returns an event list, so we can reuse the parser!
    except ValueError:
        return {"error": "Invalid date format. Please use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


# --- SPRINT FEATURE 2 ---
async def get_player_recent_matches(player_name: str) -> Dict[str, Any]:
    """Finds a player by name and fetches their recent match history."""
    logger.info(f"Tool 'get_player_recent_matches' called for player: '{player_name}'")
    player_id = await player_finder.find_player_id_by_name(player_name)

    if not player_id:
        return {
            "summary": f"I couldn't find a unique player named '{player_name}'. Please try their full name or check the spelling."}

    raw_data = await api_client.make_api_request(f"api/tennis/player/{player_id}/events/previous/0")
    return data_parser.parse_event_list(raw_data)  # Player history also returns an event list, reuse is great!


async def get_rankings(ranking_type: str) -> Dict[str, Any]:
    """Gets official world tennis rankings for either men (ATP) or women (WTA)."""
    logger.info(f"Tool 'get_rankings' called for type: {ranking_type}")
    ranking_type = ranking_type.lower()
    if ranking_type not in ["atp", "wta"]:
        return {"error": "Invalid ranking_type. Must be 'atp' or 'wta'."}

    return await api_client.make_api_request(f"api/tennis/rankings/{ranking_type}/live")


async def debug_api_search(player_name: str) -> Dict[str, Any]:
    """Directly queries the API's player search endpoint for debugging."""
    logger.info(f"--- DEBUG SEARCH --- for '{player_name}'")
    search_term_quoted = urllib.parse.quote(player_name)
    return await api_client.make_api_request(f"api/tennis/search/{search_term_quoted}")