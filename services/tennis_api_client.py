"""
Contains all functions that directly interact with the external Tennis API
and other external data sources like the current date.

This module is built for asynchronous I/O using httpx to ensure non-blocking
requests to the external Tennis API, making the application fast and scalable.
"""

import logging
import datetime
import urllib.parse
from typing import Any, Dict, Optional, List, Tuple
import asyncio
import httpx

from config import settings
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)


async def _make_request_async(full_url_path: str) -> Dict[str, Any]:
    """
    Performs an asynchronous GET request to the Tennis API.
    """
    url = f"https://{settings.tennis_api_host}/{full_url_path}"
    headers = {
        "X-RapidAPI-Key": settings.tennis_api_key,
        "X-RapidAPI-Host": settings.tennis_api_host,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as http_err:
        logger.error(f"HTTP error for {url}: {http_err.response.status_code} - {http_err.response.text}", exc_info=True)
        return {
            "error": f"API request failed with status {http_err.response.status_code}. Response: {http_err.response.text}"}
    except httpx.RequestError as req_err:
        logger.error(f"Request error for {url}: {req_err}", exc_info=True)
        return {"error": "Could not connect to the Tennis API."}
    except ValueError:
        logger.error(f"Failed to decode JSON from {url}", exc_info=True)
        return {"error": "Received invalid data from the Tennis API."}


def _process_event_list(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    if "error" in raw_data:
        return raw_data
    try:
        events = raw_data.get("events", [])
        if not events:
            return {"summary": "No events found for this query."}
        MAX_EVENTS_TO_PROCESS = 25
        simplified_events = []
        for event in events[:MAX_EVENTS_TO_PROCESS]:
            tournament_info = event.get("tournament", {})
            home_team_info = event.get("homeTeam", {})
            away_team_info = event.get("awayTeam", {})
            status_info = event.get("status", {})
            home_score_info = event.get("homeScore", {})
            away_score_info = event.get("awayScore", {})

            simplified_event = {
                "tournament": tournament_info.get("name"),
                "category": (tournament_info.get("category") or {}).get("name"),
                "home_player": home_team_info.get("name"),
                "away_player": away_team_info.get("name"),
                "status": status_info.get("description", "Scheduled"),
                "event_id": event.get("id"),
                "home_score": home_score_info,
                "away_score": away_score_info,
            }
            simplified_events.append(simplified_event)
        return {
            "total_events_found": len(events),
            "events_returned": len(simplified_events),
            "events_preview": simplified_events,
        }
    except Exception as e:
        logger.error(f"Failed to process API response data: {e}", exc_info=True)
        return {"error": "Failed to parse the data from the Tennis API."}


def _simplify_match_data(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes the full, complex event and statistics data and returns a clean,
    concise summary perfect for an LLM.
    """
    try:
        home_score = event_data.get("home_score", {})
        away_score = event_data.get("away_score", {})

        winner_code = event_data.get("winnerCode", home_score.get("winnerCode", away_score.get("winnerCode")))

        winner_name = "N/A"
        if winner_code == 1:
            winner_name = event_data.get("home_player")
        elif winner_code == 2:
            winner_name = event_data.get("away_player")

        score_summary = []
        for i in range(1, 6):
            period_key = f"period{i}"
            if period_key in home_score and period_key in away_score:
                score_summary.append(f"{home_score.get(period_key)}-{away_score.get(period_key)}")

        final_score_str = ", ".join(score_summary) if score_summary else "Score not available"

        stats = {}
        all_stats_period = next((p for p in event_data.get("statistics", []) if p.get("period") == "ALL"), None)
        if all_stats_period:
            for group in all_stats_period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    key = item.get("key")
                    if key in ["aces", "doubleFaults", "breakPointsSaved", "breakPointsConverted"]:
                        stats[key] = {
                            "home": item.get("home"),
                            "away": item.get("away")
                        }

        return {
            "tournament": event_data.get("tournament"),
            "home_player": event_data.get("home_player"),
            "away_player": event_data.get("away_player"),
            "status": event_data.get("status"),
            "winner": winner_name,
            "final_score": final_score_str,
            "simplified_statistics": stats if stats else "No detailed statistics available."
        }
    except Exception as e:
        logger.error(f"Error simplifying match data: {e}", exc_info=True)
        return {"error": "Failed to parse and simplify match data."}


async def _find_and_process_specific_match(events: List[Dict], player1_name: str, player2_name: Optional[str]) -> Optional[Dict]:
    """Internal helper to find a specific match in a list of events and get its stats."""
    target_event = None
    p1_lower = player1_name.lower()
    p2_lower = player2_name.lower() if player2_name else None

    for event in events:
        home_player = event.get("home_player", "").lower()
        away_player = event.get("away_player", "").lower()
        p1_in_match = p1_lower in home_player or p1_lower in away_player
        p2_in_match = not p2_lower or (p2_lower in home_player or p2_lower in away_player)

        if p1_in_match and p2_in_match:
            target_event = event
            logger.info(f"Found target match: {target_event}")
            break

    if not target_event:
        return None

    event_id = target_event.get("event_id")
    if not event_id:
        return {"error": "Found the match, but could not retrieve its details due to missing data."}

    logger.info(f"Found event_id {event_id}, now fetching detailed statistics.")
    stats_data = await get_event_statistics(str(event_id))

    target_event.update(stats_data)
    simplified_data = _simplify_match_data(target_event)
    return {
        "summary": "Successfully found and processed match details.",
        "match_details": simplified_data
    }


async def find_match_and_get_details(player1_name: str, player2_name: Optional[str] = None,
                                     date: Optional[str] = None) -> Dict[str, Any]:
    logger.info(f"Universal match search for P1='{player1_name}', P2='{player2_name}', Date='{date}'")
    search_desc = f"'{player1_name}'" + (f" vs '{player2_name}'" if player2_name else "")

    # --- DYNAMIC LOGIC ---
    # Case 1: A specific date is provided.
    if date:
        logger.info(f"Date '{date}' provided. Searching that day's schedule.")
        daily_events_data = await get_general_schedule(date)
        if "error" in daily_events_data:
            return daily_events_data
        events = daily_events_data.get("events_preview", [])
        if not events:
            return {"summary": f"I couldn't find any matches at all scheduled for {date}."}

        match_details = await _find_and_process_specific_match(events, player1_name, player2_name)
        if match_details:
            return match_details
        else:
            logger.warning(f"Could not find a match for {search_desc} in the schedule for {date}.")
            return {"summary": f"I looked for a match with {search_desc} on {date} but couldn't find one."}

    # Case 2: No date provided. This is where we get smart.
    if not date:
        # Step 2a: Check for a LIVE match first. This is for "what's the score right now" queries.
        logger.info("No date provided. Checking for LIVE matches first.")
        live_events_data = await get_live_events()
        live_events = live_events_data.get("events_preview", [])
        if live_events:
            live_match_details = await _find_and_process_specific_match(live_events, player1_name, player2_name)
            if live_match_details:
                logger.info(f"Found LIVE match for {search_desc}. Returning immediately.")
                return live_match_details

        # Step 2b: No live match found. Now, look for recent H2H matches to ask for clarification.
        logger.info(f"No live match found for {search_desc}. Looking up H2H for clarification.")
        if not player2_name:
            return {"summary": "To find a past match without a date, please provide two player names."}

        h2h_data = await get_h2h_events(player1_name, player2_name)
        if h2h_data.get("recent_matches"):
            return {
                "summary": f"I couldn't find a live match, but I found several recent matches for {player1_name} and {player2_name}. Please ask the user to clarify which one they are interested in.",
                "clarification_options": h2h_data["recent_matches"]
            }
        else:
            # Return the summary from the H2H call (e.g., "no matches found")
            return h2h_data


async def debug_api_search(player_name: str) -> Dict[str, Any]:
    search_term_quoted = urllib.parse.quote(player_name)
    full_path = f"api/tennis/search/{search_term_quoted}"
    logger.info(f"--- DEBUG SEARCH ---: Making raw request for '{player_name}' to full path '{full_path}'")
    return await _make_request_async(full_path)


async def _find_player_id_by_name(player_name: str) -> Optional[int]:
    """Finds a player's ID using a multi-strategy search."""
    logger.info(f"Attempting to find player ID for: '{player_name}'")

    original_name_parts = player_name.lower().split()

    search_terms = [player_name]
    if len(original_name_parts) > 1:
        search_terms.append(original_name_parts[-1])
        search_terms.append(original_name_parts[0])

    for term in set(search_terms):
        logger.info(f"Search Strategy: Trying term '{term}'")
        search_data = await _make_request_async(f"api/tennis/search/{urllib.parse.quote(term)}")

        if "error" in search_data or not search_data.get("results"):
            continue

        for result in search_data.get("results", []):
            entity = result.get("entity", {})
            if result.get("type") != "player" or (entity.get("sport", {}).get("name") != "Tennis"):
                continue

            api_name = entity.get("name", "").lower()
            if all(part in api_name for part in original_name_parts):
                player_id = entity.get("id")
                if isinstance(player_id, int):
                    logger.info(f"SUCCESS: Found ID {player_id} for '{player_name}' (via term '{term}', API name '{api_name}')")
                    return player_id

    logger.error(f"All search strategies failed for '{player_name}'.")
    return None


async def get_h2h_events(player1_name: str, player2_name: str) -> Dict[str, Any]:
    logger.info(f"H2H: Starting lookup for '{player1_name}' vs '{player2_name}'")
    player1_id, player2_id = await asyncio.gather(
        _find_player_id_by_name(player1_name),
        _find_player_id_by_name(player2_name)
    )

    if not all([player1_id, player2_id]):
        failed_player = player1_name if not player1_id else player2_name
        logger.warning(f"Could not find a unique player ID for '{failed_player}'.")
        return {"summary": f"I had trouble finding a player named '{failed_player}' in my records. Could you try their full name?"}

    h2h_data = await _make_request_async(f"api/tennis/player/{player1_id}/h2h/{player2_id}")
    if "error" in h2h_data or not h2h_data.get("events"):
        logger.warning(f"H2H API call failed for players {player1_id} and {player2_id}.")
        return {"summary": f"I couldn't find any head-to-head match history between {player1_name} and {player2_name}."}

    return await _process_h2h_data_and_return(h2h_data, player1_id, player2_id, player1_name, player2_name)


async def _process_h2h_data_and_return(h2h_data: Dict[str, Any], player1_id: int, player2_id: int, player1_name: str, player2_name: str) -> Dict[str, Any]:
    try:
        player1_canonical_name, player2_canonical_name = player1_name, player2_name
        h2h_events = h2h_data.get("events", [])
        p1_wins, p2_wins = 0, 0

        if h2h_events:
            first_event = h2h_events[0]
            home_team = first_event.get("homeTeam", {})
            away_team = first_event.get("awayTeam", {})
            if home_team.get("id") == player1_id: player1_canonical_name = home_team.get("name", player1_name)
            if away_team.get("id") == player2_id: player2_canonical_name = away_team.get("name", player2_name)

        for match in h2h_events:
            winner_code = match.get("winnerCode")
            home_id = match.get("homeTeam", {}).get("id")
            if winner_code == 1 and home_id == player1_id: p1_wins += 1
            elif winner_code == 1 and home_id == player2_id: p2_wins += 1
            elif winner_code == 2 and match.get("awayTeam", {}).get("id") == player1_id: p1_wins += 1
            elif winner_code == 2 and match.get("awayTeam", {}).get("id") == player2_id: p2_wins += 1

        recent_matches = []
        for match in h2h_events[:3]:
            winner_name = "N/A"
            if match.get("winnerCode") == 1: winner_name = match.get("homeTeam", {}).get("name")
            elif match.get("winnerCode") == 2: winner_name = match.get("awayTeam", {}).get("name")
            timestamp = match.get("startTimestamp")
            match_date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d') if timestamp else "N/A"
            score_parts = [f"{match.get('homeScore',{}).get(f'period{i}')}-{match.get('awayScore',{}).get(f'period{i}')}" for i in range(1, 6) if match.get('homeScore',{}).get(f'period{i}')]
            recent_matches.append({"date": match_date, "tournament": match.get("tournament", {}).get("name"), "winner": winner_name, "score": ", ".join(score_parts) or "N/A"})

        summary_text = f"The head-to-head record between {player1_canonical_name} and {player2_canonical_name} is tied {p1_wins}-{p1_wins}."
        if p1_wins > p2_wins: summary_text = f"{player1_canonical_name} leads {player2_canonical_name} {p1_wins}-{p2_wins} in their head-to-head matches."
        elif p2_wins > p1_wins: summary_text = f"{player2_canonical_name} leads {player1_canonical_name} {p2_wins}-{p1_wins} in their head-to-head matches."

        logger.info(f"Successfully processed H2H data: {summary_text}")
        return {"summary": summary_text, "overall_record": {f"{player1_canonical_name}_wins": p1_wins, f"{player2_canonical_name}_wins": p2_wins}, "recent_matches": recent_matches}
    except Exception as e:
        logger.critical(f"Failed to parse H2H response: {e}", exc_info=True)
        return await perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")


async def get_general_schedule(date: str) -> Dict[str, Any]:
    """ Renamed from get_scheduled_events_by_date """
    try:
        date_map = {'today': 0, 'tomorrow': 1, 'yesterday': -1}
        delta = date_map.get(date.lower())
        if delta is not None:
            target_date = datetime.date.today() + datetime.timedelta(days=delta)
        else:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        api_date_str = f"{target_date.day}/{target_date.month}/{target_date.year}"
        return _process_event_list(await _make_request_async(f"api/tennis/events/{api_date_str}"))
    except ValueError:
        return {"error": "Invalid date format. Please use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


async def get_live_events() -> Dict[str, Any]:
    """ This is now primarily an internal helper function. """
    return _process_event_list(await _make_request_async("api/tennis/events/live"))


async def get_odds_by_date(date: str) -> Dict[str, Any]:
    try:
        date_map = {'today': 0, 'tomorrow': 1, 'yesterday': -1}
        delta = date_map.get(date.lower())
        if delta is not None:
            target_date = datetime.date.today() + datetime.timedelta(days=delta)
        else:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        api_date_str = f"{target_date.day}/{target_date.month}/{target_date.year}"
        return _process_event_list(await _make_request_async(f"api/tennis/events/odds/{api_date_str}"))
    except ValueError:
        return {"error": "Invalid date format. Use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


async def get_event_statistics(event_id: str) -> Dict[str, Any]:
    """ This is now primarily an internal helper function. """
    return await _make_request_async(f"api/tennis/event/{event_id}/statistics")


async def get_player_performance(player_id: str) -> Dict[str, Any]:
    """ This is now primarily an internal helper function. """
    return _process_event_list(await _make_request_async(f"api/tennis/player/{player_id}/events/previous/0"))


async def get_rankings(ranking_type: str) -> Dict[str, Any]:
    ranking_type = ranking_type.lower()
    if ranking_type not in ["atp", "wta"]:
        return {"error": "Invalid ranking_type. Must be 'atp' or 'wta'."}
    return await _make_request_async(f"api/tennis/rankings/{ranking_type}/live")