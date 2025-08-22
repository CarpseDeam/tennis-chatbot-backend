# core/tools/web_search.py
"""
Defines the web search tool for the LLM.
"""
import logging
import httpx
from config import settings

# --- THIS IS THE CORRECT IMPORT AND IMPLEMENTATION ---
# The required classes are in the 'protos' module.
from google.generativeai import protos

logger = logging.getLogger(__name__)

# This schema is now built using the correct, verified proto classes.
# The FunctionDeclaration must be wrapped inside a protos.Tool object.
SEARCH_TOOL_SCHEMA = protos.Tool(
    function_declarations=[
        protos.FunctionDeclaration(
            name="web_search",
            description="Searches the web for up-to-date information on a given topic, especially for recent tennis matches, player rankings, or news.",
            parameters=protos.Schema(
                type=protos.Type.OBJECT,
                properties={
                    "query": protos.Schema(type=protos.Type.STRING, description="The precise search query to use.")
                },
                required=["query"]
            )
        )
    ]
)


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
        'num': 5
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        search_results = response.json()
        items = search_results.get("items", [])

        if not items:
            return "No relevant results found on the web for that query."

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