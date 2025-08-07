# services/tennis_logic/data_parser.py
"""
This module is the data-cleaning expert. Its sole responsibility is to
take raw, complex JSON data from the Tennis API and parse, process, and
simplify it into a clean, predictable format suitable for the LLM.
"""
import logging
import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def parse_event_list(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes a raw API response containing a list of events into a simplified summary.

    Args:
        raw_data (Dict[str, Any]): The raw JSON dictionary from the API.

    Returns:
        Dict[str, Any]: A structured dictionary with a summary of events.
    """
    if "error" in raw_data:
        return raw_data
    try:
        events = raw_data.get("events", [])
        if not events:
            return {"summary": "No events found for this query."}

        simplified_events = []
        # Limit the number of events to process to avoid overloading the context
        for event in events[:25]:
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
        logger.error(f"Failed to process event list data: {e}", exc_info=True)
        return {"error": "Failed to parse the event list from the Tennis API."}


def simplify_full_match_details(full_event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes a rich event object (already combined with stats) and creates the
    final, concise summary for the LLM.

    Args:
        full_event_data (Dict[str, Any]): A dictionary representing a single match,
                                          already merged with its statistics.

    Returns:
        Dict[str, Any]: A clean, LLM-friendly summary of the match.
    """
    try:
        home_score = full_event_data.get("home_score", {})
        away_score = full_event_data.get("away_score", {})

        winner_code = full_event_data.get("winnerCode", home_score.get("winnerCode", away_score.get("winnerCode")))

        winner_name = "N/A"
        if winner_code == 1:
            winner_name = full_event_data.get("home_player")
        elif winner_code == 2:
            winner_name = full_event_data.get("away_player")

        score_summary = []
        for i in range(1, 6):
            period_key = f"period{i}"
            if period_key in home_score and period_key in away_score:
                score_summary.append(f"{home_score.get(period_key)}-{away_score.get(period_key)}")
        final_score_str = ", ".join(score_summary) if score_summary else "Score not available"

        stats = {}
        all_stats_period = next((p for p in full_event_data.get("statistics", []) if p.get("period") == "ALL"), None)
        if all_stats_period:
            for group in all_stats_period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    key = item.get("key")
                    if key in ["aces", "doubleFaults", "breakPointsSaved", "breakPointsConverted"]:
                        stats[key] = {"home": item.get("home"), "away": item.get("away")}

        return {
            "tournament": full_event_data.get("tournament"),
            "home_player": full_event_data.get("home_player"),
            "away_player": full_event_data.get("away_player"),
            "status": full_event_data.get("status"),
            "winner": winner_name,
            "final_score": final_score_str,
            "simplified_statistics": stats if stats else "No detailed statistics available."
        }
    except Exception as e:
        logger.error(f"Error simplifying match data: {e}", exc_info=True)
        return {"error": "Failed to parse and simplify match data."}


def parse_h2h_data(h2h_data: Dict[str, Any], p1_id: int, p2_id: int, p1_name: str, p2_name: str) -> Dict[str, Any]:
    """
    Parses the raw Head-to-Head API response into a structured summary.

    Args:
        h2h_data (Dict[str, Any]): The raw JSON from the H2H API endpoint.
        p1_id (int): The ID of player 1.
        p2_id (int): The ID of player 2.
        p1_name (str): The name of player 1.
        p2_name (str): The name of player 2.

    Returns:
        Dict[str, Any]: A structured summary of the H2H record and recent matches.
    """
    try:
        p1_canonical, p2_canonical = p1_name, p2_name
        h2h_events = h2h_data.get("events", [])
        p1_wins, p2_wins = 0, 0

        # Determine canonical names from the first event if available
        if h2h_events:
            home_team = h2h_events[0].get("homeTeam", {})
            away_team = h2h_events[0].get("awayTeam", {})
            if home_team.get("id") == p1_id: p1_canonical = home_team.get("name", p1_name)
            if away_team.get("id") == p2_id: p2_canonical = away_team.get("name", p2_name)

        # Calculate wins
        for match in h2h_events:
            winner_code = match.get("winnerCode")
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            if winner_code == 1 and home_id == p1_id: p1_wins += 1
            elif winner_code == 1 and home_id == p2_id: p2_wins += 1
            elif winner_code == 2 and away_id == p1_id: p1_wins += 1
            elif winner_code == 2 and away_id == p2_id: p2_wins += 1

        # Summarize recent matches
        recent_matches = []
        for match in h2h_events[:3]:
            home_score = match.get("homeScore", {})
            away_score = match.get("awayScore", {})
            score_parts = [f"{home_score[f'period{i}']}-{away_score[f'period{i}']}" for i in range(1, 6) if home_score.get(f'period{i}')]
            recent_matches.append({
                "date": datetime.datetime.fromtimestamp(match["startTimestamp"]).strftime('%Y-%m-%d') if match.get("startTimestamp") else "N/A",
                "tournament": match.get("tournament", {}).get("name"),
                "winner": match.get("homeTeam", {}).get("name") if match.get("winnerCode") == 1 else match.get("awayTeam", {}).get("name"),
                "score": ", ".join(score_parts) or "Score not available"
            })

        # Create final summary text
        if p1_wins > p2_wins: summary = f"{p1_canonical} leads {p2_canonical} {p1_wins}-{p2_wins} in their head-to-head."
        elif p2_wins > p1_wins: summary = f"{p2_canonical} leads {p1_canonical} {p2_wins}-{p1_wins} in their head-to-head."
        else: summary = f"The head-to-head record between {p1_canonical} and {p2_canonical} is tied {p1_wins}-{p1_wins}."

        logger.info(f"Successfully parsed H2H data: {summary}")
        return {
            "summary": summary,
            "overall_record": {f"{p1_canonical}_wins": p1_wins, f"{p2_canonical}_wins": p2_wins},
            "recent_matches": recent_matches
        }
    except Exception as e:
        logger.critical(f"Critical failure while parsing H2H response: {e}", exc_info=True)
        return {"error": "Failed to parse H2H data."}