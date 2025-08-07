# services/tennis_logic/api_client.py
"""
This module is solely responsible for making the raw API requests to the
external Tennis API. It handles authentication, headers, and basic error
handling for the HTTP communication layer.
"""
import logging
from typing import Any, Dict

import httpx
from config import settings

logger = logging.getLogger(__name__)


async def make_api_request(full_url_path: str) -> Dict[str, Any]:
    """
    Performs an asynchronous GET request to the Tennis API.

    Args:
        full_url_path (str): The specific API path to request (e.g., "api/tennis/events/live").

    Returns:
        Dict[str, Any]: The JSON response from the API or a dictionary with an error key.
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
    except ValueError:  # Catches JSON decoding errors
        logger.error(f"Failed to decode JSON from {url}", exc_info=True)
        return {"error": "Received invalid data from the Tennis API."}
