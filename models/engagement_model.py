"""This file chooses which engagement model to run."""

from config import ENGAGEMENT_MODEL_NAME
from models.fuzzy_model import predict_engagement as fuzzy_predict
from models.hmm_model import predict_engagement as hmm_predict

# run the chosen engagement model from config and return the predicted engagement label and score
def predict_engagement(features: dict, previous_state_data: dict | None = None) -> dict:
    if ENGAGEMENT_MODEL_NAME == "fuzzy":
        return fuzzy_predict(features)

    if ENGAGEMENT_MODEL_NAME == "hmm":
        return hmm_predict(features, previous_state_data)

    raise ValueError(f"Unknown engagement model: {ENGAGEMENT_MODEL_NAME}")