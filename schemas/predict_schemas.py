# schemas/predict_schemas.py
"""
Defines the Pydantic data models (Data Contracts) for the prediction API.

By centralizing these models here, we avoid circular import errors and establish
a single source of truth for the data structures used in the prediction flow.
"""
from pydantic import BaseModel, Field
from typing import Literal

class PlayerData(BaseModel):
    """Defines the clean, internal data structure for a single player."""
    rank: int = Field(..., example=10)
    points: int = Field(..., example=3000)
    age: float | None = Field(None, example=25.5)
    height: int | None = Field(None, example=185)
    plays_right_handed: bool | None = Field(None, example=True)

class MatchData(BaseModel):
    """Defines the clean, internal structure representing a match for prediction."""
    player1: PlayerData
    player2: PlayerData
    surface: Literal['Clay', 'Hard', 'Grass', 'Carpet'] = Field(..., example='Hard')
    best_of: int = Field(..., example=3)

class PredictionResponse(BaseModel):
    """Defines the structure for the prediction endpoint's response."""
    predicted_winner: Literal['Player 1', 'Player 2']
    p1_win_probability: float = Field(..., example=0.6238)