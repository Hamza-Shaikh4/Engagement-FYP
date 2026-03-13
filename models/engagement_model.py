# models/engagement_model.py

from config import ENGAGEMENT_MODEL_NAME
from models.fuzzy_model import predict_engagement as fuzzy_predict
from models.hmm_model import predict_engagement as hmm_predict


def predict_engagement(features: dict, previous_state_data: dict | None = None) -> dict:
    """
    Choose which engagement model to run.
    """
    if ENGAGEMENT_MODEL_NAME == "fuzzy":
        return fuzzy_predict(features)

    if ENGAGEMENT_MODEL_NAME == "hmm":
        return hmm_predict(features, previous_state_data)

    raise ValueError(f"Unknown engagement model: {ENGAGEMENT_MODEL_NAME}")