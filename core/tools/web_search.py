# core/tools/web_search.py
"""
Defines the web search tool for the LLM.

This module provides a function that connects to the Google Custom Search API
to find real-time information on the web. The results are formatted into a
clean string that the LLM can easily understand and use to answer questions.
"""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

# This is the schema that tells the LLM how to use our tool.
# It's defined here so it's co-located with the function itself.
SEARCH_TOOL_SCHEMA = {
    "name": "web_search",
    "description": "Searches the web for information about tennis players, tournaments, rankings, and recent news.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find information on the web. Should be a targeted question or search term."
            }
        },
        "required": ["query"]
    }
}


async def google_search(query: str) -> str:
    """
    Performs a Google search using the Custom Search API and returns formatted results.
    """
    if not settings.google_search_api_key or not settings.google_cse_id:
        logger.warning("Google Search API keys are not configured. Search tool is disabled.")
        return "Search is not available because the API keys are not configured."

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': settings.google_search_api_key,
        'cx': settings.google_cse_id,
        'q': query,
        'num': 5  # Get the top 5 results
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()  # Will raise an exception for 4xx/5xx responses

        search_results = response.json()
        items = search_results.get("items", [])

        if not items:
            return "No relevant results found on the web for that query."

        # Format the results into a string for the LLM
        formatted_results = []
        for i, item in enumerate(items):
            result = (
                f"Result {i + 1}:\n"
                f"Title: {item.get('title', 'N/A')}\n"
                f"Link: {item.get('link', 'N/A')}\n"
                f"Snippet: {item.get('snippet', 'N/A')}\n"
            )
            formatted_results.append(result)

        return "\n---\n".join(formatted_results)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred during Google Search: {e.response.text}")
        return f"An error occurred while searching: HTTP {e.response.status_code}"
    except Exception as e:
        logger.error(f"An unexpected error occurred during Google Search: {e}", exc_info=True)
        return "An unexpected error occurred while trying to search the web."