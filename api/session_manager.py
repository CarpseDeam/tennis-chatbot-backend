# api/session_manager.py
"""
Manages conversation sessions in memory.

This is a simple in-memory storage. For production, consider using
a more persistent and scalable solution like Redis.
"""
import logging
from typing import Dict, List
from schemas.chat_schemas import ChatMessage

logger = logging.getLogger(__name__)

# In-memory storage for chat histories. {session_id: [messages]}
_chat_histories: Dict[str, List[ChatMessage]] = {}

# Keep last 20 messages (10 turns) to prevent memory overflow
MAX_HISTORY_LENGTH = 20


def get_history(session_id: str) -> List[ChatMessage]:
    """Retrieves the history for a given session ID."""
    if session_id:
        logger.info(f"Retrieving history for session_id: {session_id}")
        # Return a copy to prevent accidental modification of the stored history
        return _chat_histories.get(session_id, []).copy()
    return []


def update_history(session_id: str, user_query: ChatMessage, model_response_content: str):
    """
    Appends the latest user query and model response to the session history.
    Enforces a maximum history length.
    """
    if not session_id:
        return

    # Get or create the history list for the session
    history = _chat_histories.setdefault(session_id, [])

    model_response = ChatMessage(role="model", content=model_response_content)

    history.append(user_query)
    history.append(model_response)

    # Trim history to keep it from growing indefinitely
    if len(history) > MAX_HISTORY_LENGTH:
        _chat_histories[session_id] = history[-MAX_HISTORY_LENGTH:]
        logger.info(f"History for session_id '{session_id}' trimmed to last {MAX_HISTORY_LENGTH} messages.")

    logger.info(f"History updated for session_id '{session_id}'. New length: {len(history)}")


def clear_history(session_id: str):
    """Clears the history for a given session ID."""
    if session_id and session_id in _chat_histories:
        del _chat_histories[session_id]
        logger.info(f"History cleared for session_id: {session_id}")