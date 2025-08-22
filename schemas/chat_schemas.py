# schemas/chat_schemas.py
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Represents a single message in the conversation history."""
    role: str = Field(..., examples=["user", "model"])
    content: str

class ChatRequest(BaseModel):
    """Defines the structure for a chat request body."""
    query: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = Field(default=None)
    # The default_factory ensures a new empty list is created if history is not provided.
    history: List[ChatMessage] = Field(default_factory=list)

class ChatResponse(BaseModel):
    """Defines the structure for a non-streaming chat response body."""
    response: str