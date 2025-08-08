# services/web_search_client.py

import logging
from typing import Dict, Any, List

import httpx
from config import settings

logger = logging.getLogger(__name__)

# The base URL for the Google Custom Search JSON API
BASE_URL = "https://www.googleapis.com/customsearch/v1"


async def perform_web_search(query: str) -> Dict[str, Any]:
    """
    Performs a live web search using the official Google Custom Search JSON API.

    This function is asynchronous, robust, and relies on configured API keys.
    If keys are not provided, the application will fail on startup.
    """
    logger.info(f"Performing API-based Google Search for query: '{query}'")

    # API Request Parameters
    params = {
        "key": settings.google_search_api_key,
        "cx": settings.google_cse_id,
        "q": query,
        "num": 5  # Request the top 5 results
    }

    try:
        # Use httpx.AsyncClient for non-blocking, asynchronous I/O
        async with httpx.AsyncClient() as client:
            response = await client.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            search_results = response.json()

        # --- Process the API Response ---
        items: List[Dict[str, Any]] = search_results.get("items", [])

        if not items:
            logger.warning(f"Google Search for '{query}' yielded no results.")
            return {"summary": "I searched but couldn't find any relevant information."}

        # Format the results into a clean context string for the LLM
        context_snippets = []
        for item in items:
            title = item.get("title", "No Title")
            snippet = item.get("snippet", "No Snippet Available").replace("\n", " ")
            context_snippets.append(f"Title: {title}\nSnippet: {snippet}")

        full_context = "\n\n".join(context_snippets)
        logger.info(f"Successfully retrieved {len(context_snippets)} snippets from Google Search.")

        # Return the raw context for the LLM to process
        return {
            "context": full_context,
            "source": "Google Custom Search API"
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during Google Search: {e.response.status_code} - {e.response.text}", exc_info=True)
        return {"error": f"The web search service returned an error: {e.response.status_code}"}
    except httpx.RequestError as e:
        logger.error(f"Network error during Google Search: {e}", exc_info=True)
        return {"error": f"Failed to connect to the web search service: {str(e)}"}
    except Exception as e:
        logger.error(f"An unexpected error occurred during Google Search: {e}", exc_info=True)
        return {"error": "An unexpected error occurred while trying to search the web."}