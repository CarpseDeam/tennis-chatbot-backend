"""
Contains all functions that directly interact with the external Tennis API
and other external data sources like the current date.
"""

import logging
import datetime
import urllib.parse
from typing import Any, Dict, Optional, List, Tuple

import requests

from config import settings
from services.web_search_client import perform_web_search

logger = logging.getLogger(__name__)


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


def _make_request(full_url_path: str) -> Dict[str, Any]:
    url = f"https://{settings.tennis_api_host}/{full_url_path}"
    headers = {
        "X-RapidAPI-Key": settings.tennis_api_key,
        "X-RapidAPI-Host": settings.tennis_api_host,
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error for {url}: {http_err.response.status_code} - {http_err.response.text}", exc_info=True)
        return {
            "error": f"API request failed with status {http_err.response.status_code}. Response: {http_err.response.text}"}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error for {url}: {req_err}", exc_info=True)
        return {"error": "Could not connect to the Tennis API."}
    except ValueError:
        logger.error(f"Failed to decode JSON from {url}", exc_info=True)
        return {"error": "Received invalid data from the Tennis API."}


def find_match_and_get_details(player1_name: str, date: str, player2_name: Optional[str] = None) -> Dict[str, Any]:
    """
    The definitive tool for getting details about a specific match.
    It finds a match by player(s) and date, then automatically fetches all available stats.
    """
    logger.info(f"Universal match search for player1='{player1_name}', player2='{player2_name}', date='{date}'")

    # Step 1: Get all matches for the specified day
    daily_events_data = get_scheduled_events_by_date(date)
    if "error" in daily_events_data:
        return daily_events_data

    events = daily_events_data.get("events_preview", [])
    if not events:
        return {"summary": f"I couldn't find any matches at all scheduled for {date}."}

    # Step 2: Find the specific match in the day's schedule
    target_event = None
    p1_lower = player1_name.lower()
    p2_lower = player2_name.lower() if player2_name else None

    for event in events:
        home_player = event.get("home_player", "").lower()
        away_player = event.get("away_player", "").lower()

        # Check if players are in this event
        p1_in_match = p1_lower in home_player or p1_lower in away_player
        p2_in_match = True
        if p2_lower:
            p2_in_match = p2_lower in home_player or p2_lower in away_player

        if p1_in_match and p2_in_match:
            target_event = event
            logger.info(f"Found target match: {target_event}")
            break

    if not target_event:
        search_desc = f"'{player1_name}'"
        if player2_name:
            search_desc += f" vs '{player2_name}'"
        logger.warning(f"Could not find a match for {search_desc} in the schedule for {date}.")
        return {"summary": f"I looked for a match with {search_desc} on {date} but couldn't find one. They may not have played, or the data isn't in my system."}

    # Step 3: If match is found, get its detailed statistics
    event_id = target_event.get("event_id")
    if not event_id:
        logger.error(f"Match found but it's missing an event_id: {target_event}")
        return {"error": "Found the match, but could not retrieve its details due to missing data."}

    logger.info(f"Found event_id {event_id}, now fetching detailed statistics.")
    stats_data = get_event_statistics(str(event_id))

    if "error" in stats_data:
        logger.warning(f"Could get match details but failed to get stats for event {event_id}. Returning base info.")
        # Return the match info we have, even if stats fail
        return {
            "summary": "Found match details but could not get the full statistics.",
            "match_details": target_event
        }

    # Step 4: Merge the basic event data with the rich statistics
    logger.info("Successfully fetched stats, merging with event data.")
    target_event.update(stats_data)

    return {
        "summary": "Successfully found the match and its complete statistics.",
        "match_details": target_event
    }


def debug_api_search(player_name: str) -> Dict[str, Any]:
    search_term_quoted = urllib.parse.quote(player_name)
    full_path = f"api/tennis/search/{search_term_quoted}"
    logger.info(f"--- DEBUG SEARCH ---: Making raw request for '{player_name}' to full path '{full_path}'")
    return _make_request(full_path)


def _find_player_id_by_name(player_name: str) -> Optional[int]:
    logger.info(f"Attempting to find player ID for: '{player_name}'")

    def find_player_in_results(data: Dict[str, Any], name_to_match: str) -> Optional[int]:
        if "error" in data or not data.get("results"):
            logger.warning("API returned no results or an error for this search query.")
            return None

        input_name_parts = name_to_match.lower().split()

        for result in data.get("results", []):
            entity = result.get("entity", {})
            if result.get("type") == "player" and entity.get("sport", {}).get("name") == "Tennis":
                api_name = entity.get("name", "").lower()

                if all(part in api_name for part in input_name_parts):
                    player_id = entity.get("id")
                    if isinstance(player_id, int):
                        logger.info(
                            f"SUCCESS: Found player ID {player_id} for '{name_to_match}' (API name: '{api_name}')"
                        )
                        return player_id

        logger.warning(f"Could not find a matching player for '{name_to_match}' in the provided API results.")
        return None

    logger.info(f"Strategy 1: Searching API with full name '{player_name}'")
    full_name_quoted = urllib.parse.quote(player_name)
    search_data = _make_request(f"api/tennis/search/{full_name_quoted}")
    player_id = find_player_in_results(search_data, player_name)
    if player_id:
        return player_id

    name_parts = player_name.split()
    if len(name_parts) > 1:
        last_name = name_parts[-1]
        logger.info(f"Strategy 1 failed. Strategy 2: Searching API with last name only: '{last_name}'")
        last_name_quoted = urllib.parse.quote(last_name)
        search_data = _make_request(f"api/tennis/search/{last_name_quoted}")

        player_id = find_player_in_results(search_data, player_name)
        if player_id:
            return player_id

    logger.error(f"All search strategies failed for '{player_name}'.")
    return None


def _get_past_months(num_months: int) -> List[Tuple[int, int]]:
    months = []
    today = datetime.date.today()
    for i in range(num_months):
        current_month, current_year = today.month - i, today.year
        while current_month <= 0:
            current_month += 12
            current_year -= 1
        months.append((current_month, current_year))
    return months


def _find_common_event_id_in_calendar(player1_id: int, player2_id: int) -> Optional[int]:
    logger.info(f"Attempting calendar scan for common event between {player1_id} and {player2_id}.")
    for month, year in _get_past_months(24):
        calendar_data = _make_request(f"api/tennis/calendar/{month}/{year}")
        if "error" in calendar_data or not calendar_data.get("events"):
            continue
        for event in calendar_data["events"]:
            p_ids = {event.get("homeTeam", {}).get("id"), event.get("awayTeam", {}).get("id")}
            if {player1_id, player2_id}.issubset(p_ids):
                event_id = event.get("id")
                logger.info(f"Found common match {event_id} in calendar scan for {month}/{year}.")
                return event_id
    logger.warning(f"Calendar scan over {len(_get_past_months(24))} months found no common event for players {player1_id} and {player2_id}.")
    return None


def get_h2h_events(player1_name: str, player2_name: str) -> Dict[str, Any]:
    logger.info(f"H2H: Starting lookup for '{player1_name}' vs '{player2_name}'")
    player1_id = _find_player_id_by_name(player1_name)
    player2_id = _find_player_id_by_name(player2_name)

    if not all([player1_id, player2_id]):
        logger.warning(f"Could not find IDs for one or both players. Falling back to web search.")
        return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")

    event_id_for_duel = None
    logger.info(f"Attempting to find H2H event in {player1_name}'s recent match history.")
    history_data = _make_request(f"api/tennis/player/{player1_id}/events/previous/0")

    if "error" not in history_data and history_data.get("events"):
        for event in history_data["events"]:
            if player2_id in {event.get("homeTeam", {}).get("id"), event.get("awayTeam", {}).get("id")}:
                event_id_for_duel = event.get("id")
                if event_id_for_duel:
                    logger.info(f"Found common event {event_id_for_duel} in player history.")
                    break

    if event_id_for_duel:
        h2h_data = _make_request(f"api/tennis/event/{event_id_for_duel}/duel")
        if "error" not in h2h_data and h2h_data.get("events"):
            return _process_h2h_data_and_return(h2h_data, player1_id, player2_id, player1_name, player2_name)

    event_id_for_duel = _find_common_event_id_in_calendar(player1_id, player2_id)
    if event_id_for_duel:
        h2h_data = _make_request(f"api/tennis/event/{event_id_for_duel}/duel")
        if "error" not in h2h_data and h2h_data.get("events"):
            return _process_h2h_data_and_return(h2h_data, player1_id, player2_id, player1_name, player2_name)

    logger.warning(f"All API H2H attempts failed for {player1_name} vs {player2_name}. Falling back to web search.")
    return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")


def _process_h2h_data_and_return(h2h_data: Dict[str, Any], player1_id: int, player2_id: int, player1_name: str,
                                 player2_name: str) -> Dict[str, Any]:
    try:
        player1_canonical_name = player1_name
        player2_canonical_name = player2_name

        h2h_events = h2h_data.get("events", [])
        p1_wins, p2_wins = 0, 0

        if h2h_events:
            first_event = h2h_events[0]
            home_team = first_event.get("homeTeam", {})
            away_team = first_event.get("awayTeam", {})

            if home_team.get("id") == player1_id:
                player1_canonical_name = home_team.get("name", player1_name)
            elif home_team.get("id") == player2_id:
                player2_canonical_name = home_team.get("name", player2_name)

            if away_team.get("id") == player1_id:
                player1_canonical_name = away_team.get("name", player1_name)
            elif away_team.get("id") == player2_id:
                player2_canonical_name = away_team.get("name", player2_name)

        for match in h2h_events:
            winner_code = match.get("winnerCode")
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")

            if winner_code == 1 and home_id == player1_id: p1_wins += 1
            elif winner_code == 1 and home_id == player2_id: p2_wins += 1
            elif winner_code == 2 and away_id == player1_id: p1_wins += 1
            elif winner_code == 2 and away_id == player2_id: p2_wins += 1

        summary_text = ""
        if p1_wins > p2_wins:
            summary_text = f"{player1_canonical_name} leads {player2_canonical_name} {p1_wins}-{p2_wins} in their head-to-head matches."
        elif p2_wins > p1_wins:
            summary_text = f"{player2_canonical_name} leads {player1_canonical_name} {p2_wins}-{p1_wins} in their head-to-head matches."
        else:
            summary_text = f"{player1_canonical_name} and {player2_canonical_name} are tied {p1_wins}-{p1_wins} in their head-to-head matches."

        logger.info(f"Successfully processed H2H data: {summary_text}")
        return {"summary": summary_text,
                "data": {f"{player1_canonical_name}_wins": p1_wins, f"{player2_canonical_name}_wins": p2_wins}}
    except Exception as e:
        logger.critical(f"Failed to parse DUEL response: {e}", exc_info=True)
        return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")


def get_scheduled_events_by_date(date: str) -> Dict[str, Any]:
    try:
        date_str_lower = date.lower()
        if date_str_lower == 'today':
            target_date = datetime.date.today()
        elif date_str_lower == 'tomorrow':
            target_date = datetime.date.today() + datetime.timedelta(days=1)
        elif date_str_lower == 'yesterday':
            target_date = datetime.date.today() - datetime.timedelta(days=1)
        else:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

        api_date_str = f"{target_date.day}/{target_date.month}/{target_date.year}"
        return _process_event_list(_make_request(f"api/tennis/events/{api_date_str}"))
    except ValueError:
        return {"error": "Invalid date format. Please use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


def get_live_events() -> Dict[str, Any]:
    return _process_event_list(_make_request("api/tennis/events/live"))


def get_odds_by_date(date: str) -> Dict[str, Any]:
    try:
        date_str_lower = date.lower()
        if date_str_lower == 'today':
            target_date = datetime.date.today()
        elif date_str_lower == 'tomorrow':
            target_date = datetime.date.today() + datetime.timedelta(days=1)
        elif date_str_lower == 'yesterday':
            target_date = datetime.date.today() - datetime.timedelta(days=1)
        else:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

        api_date_str = f"{target_date.day}/{target_date.month}/{target_date.year}"
        return _process_event_list(_make_request(f"api/tennis/events/odds/{api_date_str}"))
    except ValueError:
        return {"error": "Invalid date format. Use 'today', 'tomorrow', 'yesterday', or YYYY-MM-DD."}


def get_event_statistics(event_id: str) -> Dict[str, Any]:
    return _make_request(f"api/tennis/event/{event_id}/statistics")


def get_player_performance(player_id: str) -> Dict[str, Any]:
    return _process_event_list(_make_request(f"api/tennis/player/{player_id}/events/previous/0"))


def get_rankings(ranking_type: str) -> Dict[str, Any]:
    ranking_type = ranking_type.lower()
    if ranking_type not in ["atp", "wta"]:
        return {"error": "Invalid ranking_type. Must be 'atp' or 'wta'."}
    return _make_request(f"api/tennis/rankings/{ranking_type}/live")