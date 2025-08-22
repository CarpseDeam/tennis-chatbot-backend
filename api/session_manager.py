# api/session_manager.py
"""
Manages conversation sessions using a persistent Redis backend.

This module provides an interface to store, retrieve, and update chat
histories. By using Redis, the session data survives application restarts
and deployments, making it suitable for production environments.
"""
import logging
import json
import redis
from typing import List

from config import settings
from schemas.chat_schemas import ChatMessage

logger = logging.getLogger(__name__)

# --- Redis Connection ---
try:
    # This automatically connects to the Redis instance specified in our settings
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()  # Check the connection
    logger.info("Successfully connected to Redis server.")
except redis.exceptions.ConnectionError as e:
    logger.critical(f"FATAL: Could not connect to Redis server at {settings.redis_url}. Error: {e}")
    # In a real app, you might want to handle this more gracefully,
    # but for now, we'll raise it to prevent the app from starting in a broken state.
    raise

# We use a prefix to keep our app's keys organized in Redis
SESSION_KEY_PREFIX = "chat_session:"
# Sessions will expire after 24 hours of inactivity
SESSION_TTL_SECONDS = 86400


def get_history(session_id: str) -> List[ChatMessage]:
    """Retrieves and deserializes the history for a given session ID from Redis."""
    if not session_id:
        return []

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    logger.info(f"Retrieving history from Redis for key: {key}")

    json_history = redis_client.get(key)
    if not json_history:
        return []

    # Refresh the key's expiration time since it's being used
    redis_client.expire(key, SESSION_TTL_SECONDS)

    history_data = json.loads(json_history)
    return [ChatMessage.model_validate(msg) for msg in history_data]


def _save_history(session_id: str, history: List[ChatMessage]):
    """Serializes and saves a history list to Redis."""
    if not session_id:
        return

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    # Convert Pydantic models to a list of dicts, then to a JSON string
    json_history = json.dumps([msg.model_dump() for msg in history])

    # Set the value and the expiration time
    redis_client.set(key, json_history, ex=SESSION_TTL_SECONDS)
    logger.info(f"History saved to Redis for key '{key}'.")


def set_initial_context(session_id: str, context: str):
    """
    Primes a session's history with an initial context from the system.
    This is used after the map-reduce process to give the chat a starting point.
    If a history already exists, it is cleared.
    """
    initial_message = ChatMessage(
        role="user",
        content=f"[CONTEXT] Here is the detailed analysis of the match:\n\n{context}"
    )
    history = [initial_message]
    _save_history(session_id, history)
    logger.info(f"Initial context set in Redis for session_id '{session_id}'.")


def update_history(session_id: str, user_query: ChatMessage, model_response_content: str):
    """
    Appends the latest user query and model response to the session history in Redis.
    """
    history = get_history(session_id)
    if not history:
        # This shouldn't happen in the prediction flow, but is a good safeguard
        history = []

    model_response = ChatMessage(role="model", content=model_response_content)
    history.append(user_query)
    history.append(model_response)

    _save_history(session_id, history)


def clear_history(session_id: str):
    """Clears the history for a given session ID from Redis."""
    key = f"{SESSION_KEY_PREFIX}{session_id}"
    if redis_client.exists(key):
        redis_client.delete(key)
        logger.info(f"History cleared from Redis for session_id: {session_id}")