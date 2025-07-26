# services/web_search_client.py

import logging
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
import urllib.parse

logger = logging.getLogger(__name__)

# Define headers to mimic a real web browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def perform_web_search(query: str) -> Dict[str, Any]:
    """
    Performs a REAL, live web search by scraping DuckDuckGo results.
    This function is self-contained and requires no external API keys.
    """
    logger.info(f"Performing self-hosted web scrape for query: '{query}'")

    # URL-encode the query to handle spaces and special characters
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    try:
        # Make the HTTP request to get the page content
        response = requests.get(search_url, headers=HEADERS, timeout=10)
        response.raise_for_status()  # Will raise an error for bad status codes

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all the search result snippets.
        # DuckDuckGo's simple HTML version uses a 'result' class for these.
        results = soup.find_all('div', class_='result')

        # Extract the text content from the first few results
        # to create a context for the LLM. We'll take up to 5.
        context_snippets = []
        for result in results[:5]:
            snippet = result.find('a', class_='result__snippet')
            if snippet:
                context_snippets.append(snippet.get_text(strip=True))

        if not context_snippets:
            logger.warning(f"Web scrape for '{query}' yielded no results.")
            return {"summary": "I searched the web but couldn't find any relevant information."}

        # Join the snippets into a single context string
        full_context = "\n".join(f"- {s}" for s in context_snippets)

        logger.info(f"Successfully scraped {len(context_snippets)} snippets for the query.")

        # Return the raw context for the LLM to process
        return {
            "context": full_context,
            "source": "Self-Hosted Web Scraper"
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during web scrape: {e}", exc_info=True)
        return {"error": f"Failed to connect to search engine: {str(e)}"}
    except Exception as e:
        logger.error(f"An unexpected error occurred during web scraping: {e}", exc_info=True)
        return {"error": f"An error occurred while trying to search the web."}