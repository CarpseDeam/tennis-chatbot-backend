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

        # The API gives winnerCode for the *away* team in the home player's score object sometimes.
        # We check both home and away score objects for a definitive winner code.
        winner_code = home_score.get("winnerCode", away_score.get("winnerCode"))

        winner_name = "N/A"
        if winner_code == 1:  # Home player wins
            winner_name = event_data.get("home_player")
        elif winner_code == 2:  # Away player wins
            winner_name = event_data.get("away_player")

        score_summary = []
        for i in range(1, 6):  # Check for up to 5 sets
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


async def find_match_and_get_details(player1_name: str, date: str, player2_name: Optional[str] = None) -> Dict[
    str, Any]:
    logger.info(f"Universal match search for player1='{player1_name}', player2='{player2_name}', date='{date}'")

    daily_events_data = await get_scheduled_events_by_date(date)
    if "error" in daily_events_data:
        return daily_events_data

    events = daily_events_data.get("events_preview", [])
    if not events:
        return {"summary": f"I couldn't find any matches at all scheduled for {date}."}

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
        search_desc = f"'{player1_name}'" + (f" vs '{player2_name}'" if player2_name else "")
        logger.warning(f"Could not find a match for {search_desc} in the schedule for {date}.")
        return {"summary": f"I looked for a match with {search_desc} on {date} but couldn't find one."}

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


async def debug_api_search(player_name: str) -> Dict[str, Any]:
    search_term_quoted = urllib.parse.quote(player_name)
    full_path = f"api/tennis/search/{search_term_quoted}"
    logger.info(f"--- DEBUG SEARCH ---: Making raw request for '{player_name}' to full path '{full_path}'")
    return await _make_request_async(full_path)


async def _find_player_id_by_name(player_name: str) -> Optional[int]:
    logger.info(f"Attempting to find player ID for: '{player_name}'")

    async def find_in_results(data: Dict[str, Any], name: str) -> Optional[int]:
        if "error" in data or not data.get("results"): return None
        return next((entity.get("id") for result in data.get("results", []) if
                     (entity := result.get("entity", {})) and result.get("type") == "player" and entity.get("sport",
                                                                                                            {}).get(
                         "name") == "Tennis" and all(
                         part in entity.get("name", "").lower() for part in name.lower().split()) and isinstance(
                         entity.get("id"), int)), None)

    search_data = await _make_request_async(f"api/tennis/search/{urllib.parse.quote(player_name)}")
    player_id = await find_in_results(search_data, player_name)
    if player_id: return player_id

    if len(player_name.split()) > 1:
        last_name = player_name.split()[-1]
        search_data = await _make_request_async(f"api/tennis/search/{urllib.parse.quote(last_name)}")
        player_id = await find_in_results(search_data, player_name)
        if player_id: return player_id

    logger.error(f"All search strategies failed for '{player_name}'.")
    return None


async def get_h2h_events(player1_name: str, player2_name: str) -> Dict[str, Any]:
    logger.info(f"H2H: Starting lookup for '{player1_name}' vs '{player2_name}'")
    player1_id, player2_id = await asyncio.gather(
        _find_player_id_by_name(player1_name),
        _find_player_id_by_name(player2_name)
    )

    if not all([player1_id, player2_id]):
        return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")

    h2h_data = await _make_request_async(f"api/tennis/player/{player1_id}/h2h/{player2_id}")
    if "error" in h2h_data or not h2h_data.get("events"):
        logger.warning(f"Direct H2H lookup failed. Falling back to web search.")
        return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")

    return _process_h2h_data_and_return(h2h_data, player1_id, player2_id, player1_name, player2_name)


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

            if winner_code == 1 and home_id == player1_id:
                p1_wins += 1
            elif winner_code == 1 and home_id == player2_id:
                p2_wins += 1
            elif winner_code == 2 and away_id == player1_id:
                p1_wins += 1
            elif winner_code == 2 and away_id == player2_id:
                p2_wins += 1

        recent_matches = []
        MAX_MATCHES_TO_RETURN = 5
        for match in h2h_events[:MAX_MATCHES_TO_RETURN]:
            winner_code = match.get("winnerCode")
            home_team = match.get("homeTeam", {})
            away_team = match.get("awayTeam", {})
            home_score = match.get("homeScore", {})
            away_score = match.get("awayScore", {})
            tournament = match.get("tournament", {})

            winner_name = "N/A"
            if winner_code == 1:
                winner_name = home_team.get("name")
            elif winner_code == 2:
                winner_name = away_team.get("name")

            match_date = "N/A"
            timestamp = match.get("startTimestamp")
            if timestamp:
                match_date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

            score_parts = []
            for i in range(1, 6):
                p_key = f"period{i}"
                if p_key in home_score and p_key in away_score:
                    score_parts.append(f"{home_score[p_key]}-{away_score[p_key]}")

            final_score_str = ", ".join(score_parts) if score_parts else "Score not available"

            recent_matches.append({
                "date": match_date,
                "tournament": tournament.get("name"),
                "winner": winner_name,
                "score": final_score_str
            })

        summary_text = ""
        if p1_wins > p2_wins:
            summary_text = f"{player1_canonical_name} leads {player2_canonical_name} {p1_wins}-{p2_wins} in their head-to-head matches."
        elif p2_wins > p1_wins:
            summary_text = f"{player2_canonical_name} leads {player1_canonical_name} {p2_wins}-{p1_wins} in their head-to-head matches."
        else:
            summary_text = f"The head-to-head record between {player1_canonical_name} and {player2_canonical_name} is tied {p1_wins}-{p1_wins}."

        logger.info(f"Successfully processed H2H data: {summary_text}")
        return {
            "summary": summary_text,
            "overall_record": {f"{player1_canonical_name}_wins": p1_wins, f"{player2_canonical_name}_wins": p2_wins},
            "recent_matches": recent_matches
        }
    except Exception as e:
        logger.critical(f"Failed to parse H2H response: {e}", exc_info=True)
        return perform_web_search(f"Head to head record between {player1_name} and {player2_name} tennis")


async def get_scheduled_events_by_date(date: str) -> Dict[str, Any]:
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
    return await _make_request_async(f"api/tennis/event/{event_id}/statistics")


async def get_player_performance(player_id: str) -> Dict[str, Any]:
    return _process_event_list(await _make_request_async(f"api/tennis/player/{player_id}/events/previous/0"))


async def get_rankings(ranking_type: str) -> Dict[str, Any]:
    ranking_type = ranking_type.lower()
    if ranking_type not in ["atp", "wta"]:
        return {"error": "Invalid ranking_type. Must be 'atp' or 'wta'."}
    return await _make_request_async(f"api/tennis/rankings/{ranking_type}/live")