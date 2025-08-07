# services/tennis_logic/tenipo_client.py
"""
This module is a client for the custom-built Tenipo Scraper Service.
Its only job is to fetch the live, processed data from that service's API.
"""
import logging
from typing import Any, Dict

import httpx
from config import settings

logger = logging.getLogger(__name__)


async def get_live_itf_data_from_api() -> Dict[str, Any]:
    """
    Fetches the list of all live ITF matches from our custom scraper service.
    """
    if not settings.tenipo_api_base_url:
        logger.warning("TENIPO_API_BASE_URL is not configured. Cannot fetch custom live data.")
        return {"error": "The custom scraper service is not configured on the backend."}

    url = f"{str(settings.tenipo_api_base_url).rstrip('/')}/all_live_itf_data"
    logger.info(f"Requesting live ITF data from custom service: {url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to the custom scraper service: {e}", exc_info=True)
        return {"error": f"Could not connect to the custom data service."}
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching custom ITF data: {e}", exc_info=True)
        return {"error": "An error occurred while fetching custom live data."}