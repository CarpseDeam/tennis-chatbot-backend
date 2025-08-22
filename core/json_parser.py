# core/json_parser.py

"""
This module is responsible for parsing the huge, structured JSON blob
sent by the client into a clean, validated Pydantic model that the rest of
the application can use.

This acts as a protective "extractor" layer, surgically pulling the exact
data points we need from the complex client-side object structure.
"""
import logging
from typing import Dict, Any
from datetime import datetime
from api.routers.predict import MatchData, PlayerData  # Import our target data contracts

logger = logging.getLogger(__name__)


def _find_official_ranking(rankings_list: list) -> Dict[str, Any]:
    """
    Searches the list of rankings for the official ATP ranking (type 5).
    """
    for ranking_data in rankings_list:
        if ranking_data.get('type') == 5:
            return ranking_data
    if rankings_list:
        return rankings_list[0]
    return {}


def _calculate_age(timestamp: int | None) -> float | None:
    """Calculates age in years from a UNIX timestamp."""
    if timestamp is None:
        return None
    birth_date = datetime.fromtimestamp(timestamp)
    today = datetime.now()
    # A more precise way to calculate age
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age


def _normalize_surface(ground_type: str) -> str:
    """Normalizes the 'groundType' string into one of our model's categories."""
    ground_type_lower = ground_type.lower()
    if 'clay' in ground_type_lower:
        return 'Clay'
    if 'grass' in ground_type_lower:
        return 'Grass'
    if 'carpet' in ground_type_lower:
        return 'Carpet'
    # Default to Hard for "Hardcourt outdoor", "Hardcourt indoor", etc.
    return 'Hard'


def parse_live_match_json(huge_json: Dict[str, Any]) -> MatchData:
    """
    Navigates the massive client JSON to extract the specific fields needed for prediction.
    This function is now tailored to the exact, known structure of the client's data.
    """
    logger.info("Starting to parse the huge incoming JSON blob with known schema...")
    try:
        # The client will likely assemble all .txt files into one large JSON.
        # We assume the `Event.txt` content is at the root key 'event'.
        event_data = huge_json.get('event', {})
        if not event_data:
            # A fallback if the client nests it under the filename
            event_data = huge_json.get('Event', {})

        # --- Extract Player IDs from the Event object ---
        p1_id = str(event_data.get('homeTeam', {}).get('id'))
        p2_id = str(event_data.get('awayTeam', {}).get('id'))

        if not all([p1_id, p2_id]):
            raise ValueError("Could not find player IDs in the 'event.homeTeam' or 'event.awayTeam' section.")
        logger.info(f"Found Player 1 ID: {p1_id}, Player 2 ID: {p2_id}")

        # --- Extract Data for Player 1 ---
        # The frontend will assemble the JSON with keys matching file names.
        p1_details_json = huge_json.get(f"Player Details - {p1_id}", {})
        p1_rankings_json = huge_json.get(f"Player Raking's- {p1_id}", {})

        p1_team_info = p1_details_json.get('team', {}).get('playerTeamInfo', {})
        p1_official_rank = _find_official_ranking(p1_rankings_json.get('rankings', []))

        player1 = PlayerData(
            rank=p1_official_rank.get('ranking'),
            points=p1_official_rank.get('points'),
            age=_calculate_age(p1_team_info.get('birthDateTimestamp')),
            height=int(p1_team_info.get('height', 0) * 100),
            plays_right_handed='right' in p1_team_info.get('plays', '').lower()
        )

        # --- Extract Data for Player 2 ---
        p2_details_json = huge_json.get(f"Player Details - {p2_id}", {})
        p2_rankings_json = huge_json.get(f"Player Raking's- {p2_id}", {})

        p2_team_info = p2_details_json.get('team', {}).get('playerTeamInfo', {})
        p2_official_rank = _find_official_ranking(p2_rankings_json.get('rankings', []))

        player2 = PlayerData(
            rank=p2_official_rank.get('ranking'),
            points=p2_official_rank.get('points'),
            age=_calculate_age(p2_team_info.get('birthDateTimestamp')),
            height=int(p2_team_info.get('height', 0) * 100),
            plays_right_handed='right' in p2_team_info.get('plays', '').lower()
        )

        # --- Extract Match Data using confirmed keys from Event.txt ---
        ground_type_str = event_data.get('groundType', 'Hard')
        surface = _normalize_surface(ground_type_str)
        best_of = event_data.get('defaultPeriodCount', 3)

        match_data = MatchData(
            player1=player1,
            player2=player2,
            surface=surface,
            best_of=best_of
        )

        logger.info("Successfully parsed huge JSON into clean MatchData model.")
        return match_data

    except Exception as e:
        logger.error(f"Failed to parse the huge JSON. A key or structure was missing or invalid. Error: {e}",
                     exc_info=True)
        raise ValueError(f"The incoming JSON is malformed or missing required data: {e}")