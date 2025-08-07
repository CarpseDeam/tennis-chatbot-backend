# services/tennis_logic/player_finder.py
"""
This module contains the specialized, robust logic for finding a unique
player ID based on a player's name. It handles API inconsistencies and
ambiguous results.
"""
import logging
import urllib.parse
import asyncio
from typing import Optional, Dict, Any

from .api_client import make_api_request

logger = logging.getLogger(__name__)


async def find_player_id_by_name(player_name: str) -> Optional[int]:
    """
    Finds a player's ID using a truly robust, multi-strategy search.
    This version is designed to handle name variations and API inconsistencies
    like reversed names and initials, and only returns a result if it is unambiguous.
    """
    logger.info(f"Executing robust player search for '{player_name}'.")

    # Clean the query and handle empty strings
    query_parts = set(p for p in player_name.lower().replace('.', '').split() if p)
    if not query_parts:
        return None

    # Search by full name, then by last name as a fallback.
    search_terms = [player_name]
    if len(player_name.split()) > 1:
        search_terms.append(player_name.split()[-1])

    potential_matches = []

    # Use asyncio.gather to run searches concurrently for speed.
    search_tasks = [
        make_api_request(f"api/tennis/search/{urllib.parse.quote(term)}")
        for term in set(search_terms)
    ]
    api_results = await asyncio.gather(*search_tasks)

    for search_data in api_results:
        if "error" in search_data or not search_data.get("results"):
            continue

        for result in search_data.get("results", []):
            entity = result.get("entity", {})
            if result.get("type") != "player" or not entity.get("id"):
                continue

            api_name = entity.get("name", "").lower()
            api_name_parts = set(p for p in api_name.replace(',', '').replace('.', '').split() if p)

            # DYNAMIC AND ROBUST MATCHING LOGIC
            all_parts_matched = True
            for q_part in query_parts:
                part_found = False
                for a_part in api_name_parts:
                    # Match full word, or match initial to word, or word to initial
                    if (q_part == a_part or
                            (len(a_part) == 1 and q_part.startswith(a_part)) or
                            (len(q_part) == 1 and a_part.startswith(q_part))):
                        part_found = True
                        break

                if not part_found:
                    all_parts_matched = False
                    break

            if all_parts_matched:
                potential_matches.append(entity)

    if not potential_matches:
        logger.warning(f"Robust search found NO potential matches for '{player_name}'.")
        return None

    # De-duplicate results using the unique player ID.
    unique_matches = {match['id']: match for match in potential_matches}.values()

    if len(unique_matches) == 1:
        match = list(unique_matches)[0]
        player_id = match.get("id")
        logger.info(
            f"SUCCESS: Robust search found ONE unique, confident match for '{player_name}'. ID: {player_id}, Name: {match.get('name')}")
        return player_id
    else:
        logger.warning(
            f"Robust search found {len(unique_matches)} AMBIGUOUS matches for '{player_name}'. Cannot proceed confidently.")
        for match in unique_matches:
            logger.warning(f"  - Ambiguous match found: ID {match.get('id')}, Name: {match.get('name')}")
        return None