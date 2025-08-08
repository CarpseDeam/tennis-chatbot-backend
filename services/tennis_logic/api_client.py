# services/tennis_logic/api_client.py
"""
This module is solely responsible for making the raw API requests to the
external Tennis API. It is built to be resilient, automatically retrying
on transient network errors or temporary server-side issues.
"""
import logging
from typing import Any, Dict

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

# --- Define what kind of errors are temporary and should be retried ---
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,  # Request timed out
    httpx.ConnectError,  # Could not connect to the server
)


def is_retryable_status_code(exception: BaseException) -> bool:
    """Return True if the exception is an HTTPStatusError with a 5xx status code."""
    return (
            isinstance(exception, httpx.HTTPStatusError) and
            exception.response.status_code >= 500
    )


# --- The new, hardened API request function ---
@retry(
    # Wait 2 seconds before the first retry, then 4s, then 8s, up to 30s.
    wait=wait_exponential(multiplier=2, min=2, max=30),

    # Attempt the request a total of 4 times (1 initial + 3 retries).
    stop=stop_after_attempt(4),

    # We retry on network issues OR 5xx server errors.
    retry=(retry_if_exception_type(RETRYABLE_EXCEPTIONS) | retry_if_exception_type(is_retryable_status_code)),

    # Log a warning before each retry attempt. This gives us visibility.
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying API request due to {retry_state.outcome.exception()}. "
        f"Attempt #{retry_state.attempt_number}..."
    )
)
async def make_api_request(full_url_path: str) -> Dict[str, Any]:
    """
    Performs an asynchronous, resilient GET request to the Tennis API.

    This function automatically retries on transient errors like timeouts
    or 5xx server errors, making the application more robust.

    Args:
        full_url_path (str): The specific API path to request (e.g., "api/tennis/events/live").

    Returns:
        Dict[str, Any]: The JSON response from the API.

    Raises:
        httpx.HTTPStatusError: If a 4xx client error occurs (which is not retried).
        httpx.RequestError: If a network error persists after all retries.
        ValueError: If the response is not valid JSON.
    """
    url = f"https://{settings.tennis_api_host}/{full_url_path}"
    headers = {
        "X-RapidAPI-Key": settings.tennis_api_key,
        "X-RapidAPI-Host": settings.tennis_api_host,
    }

    # Use a more granular timeout: 5s to connect, 15s total for the response.
    timeout = httpx.Timeout(15.0, connect=5.0)

    async with httpx.AsyncClient() as client:
        logger.info(f"Making API request to: {url}")
        response = await client.get(url, headers=headers, timeout=timeout)

        # Raise an exception for any 4xx or 5xx error.
        # The @retry decorator will inspect this exception to see if it should retry.
        response.raise_for_status()

        # If the code reaches here, the response was successful (2xx).
        return response.json()