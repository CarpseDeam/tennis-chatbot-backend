# api/routers/predict.py
"""
Defines the FastAPI router for the machine learning prediction endpoint.
"""
import joblib
import pandas as pd
import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

# --- IMPORTS HAVE CHANGED ---
from core.json_parser import parse_live_match_json
# Import the data contracts from their new, central location
from schemas.predict_schemas import MatchData, PredictionResponse

# --- Logger ---
logger = logging.getLogger(__name__)

# --- Configuration ---
MODEL_PATH = 'xgboost_model.joblib'
MODEL_FEATURE_BLUEPRINT = [
    'p1_rank', 'p2_rank', 'p1_points', 'p2_points', 'best_of',
    'rank_diff', 'points_diff',
    'surface_Clay', 'surface_Hard', 'surface_Grass', 'surface_Carpet',
    'p1_age', 'p1_height', 'p1_plays_right_handed',
    'p2_age', 'p2_height', 'p2_plays_right_handed'
]

# --- Router Setup ---
router = APIRouter(
    prefix="/api",
    tags=["Prediction"]
)

# --- THE PYDANTIC MODELS HAVE BEEN MOVED TO schemas/predict_schemas.py ---

# --- Model Loading ---
try:
    model = joblib.load(MODEL_PATH)
    logger.info(f"ML Model loaded successfully from '{MODEL_PATH}'")
except FileNotFoundError:
    logger.critical(f"FATAL: Model file '{MODEL_PATH}' not found. Prediction endpoint will not work.")
    model = None
except Exception as e:
    logger.critical(f"An error occurred while loading the ML model: {e}", exc_info=True)
    model = None


# --- Feature Engineering for Live Data ---
def transform_to_feature_vector(data: MatchData) -> pd.DataFrame:
    """Transforms the clean MatchData Pydantic model into a feature vector."""
    feature_dict = {
        'p1_rank': data.player1.rank,
        'p1_points': data.player1.points,
        'p1_age': data.player1.age,
        'p1_height': data.player1.height,
        'p1_plays_right_handed': data.player1.plays_right_handed,
        'p2_rank': data.player2.rank,
        'p2_points': data.player2.points,
        'p2_age': data.player2.age,
        'p2_height': data.player2.height,
        'p2_plays_right_handed': data.player2.plays_right_handed,
        'best_of': data.best_of
    }
    feature_dict['rank_diff'] = feature_dict['p1_rank'] - feature_dict['p2_rank']
    feature_dict['points_diff'] = feature_dict['p1_points'] - feature_dict['p2_points']

    feature_dict['surface_Clay'] = data.surface == 'Clay'
    feature_dict['surface_Hard'] = data.surface == 'Hard'
    feature_dict['surface_Grass'] = data.surface == 'Grass'
    feature_dict['surface_Carpet'] = data.surface == 'Carpet'

    df = pd.DataFrame([feature_dict])
    df.fillna(0, inplace=True)

    return df[MODEL_FEATURE_BLUEPRINT]


# --- Prediction Endpoint ---
@router.post("/predict", response_model=PredictionResponse)
async def predict_match(huge_request_body: Dict[str, Any]) -> PredictionResponse:
    """
    Accepts the huge, raw client JSON, parses it, runs the ML model, and returns a prediction.
    """
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The prediction model is not loaded."
        )

    try:
        clean_match_data = parse_live_match_json(huge_request_body)
        feature_vector = transform_to_feature_vector(clean_match_data)
        prediction_probabilities = model.predict_proba(feature_vector)
        p1_win_probability = prediction_probabilities[0][1]

        return PredictionResponse(
            predicted_winner="Player 1" if p1_win_probability > 0.5 else "Player 2",
            p1_win_probability=round(p1_win_probability, 4)
        )
    except ValueError as e:
        # This catches parsing errors.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred during prediction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during prediction."
        )