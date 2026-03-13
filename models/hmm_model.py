# models/hmm_model.py

"""
Simple HMM-style engagement model.

This model estimates a hidden engagement state:
- disengaged
- neutral
- engaged

using:
1. transition probabilities (how likely the state is to stay the same or change)
2. emission probabilities (how well the observed behaviour fits each state)

This version is deliberately simple so it is easier to understand and explain.
"""

from typing import Dict

# The three hidden states we want to predict
STATES = ["disengaged", "neutral", "engaged"]


def clamp_0_1(value: float) -> float:
    """Keep a value between 0 and 1."""
    return max(0.0, min(1.0, value))


def normalise(probabilities: Dict[str, float]) -> Dict[str, float]:
    """
    Convert raw scores into probabilities that sum to 1.
    """
    total = sum(probabilities.values())

    if total <= 0:
        # Fallback: equal probability if something goes wrong
        equal = 1.0 / len(probabilities)
        return {state: equal for state in probabilities}

    return {state: value / total for state, value in probabilities.items()}


def get_transition_matrix() -> Dict[str, Dict[str, float]]:
    """
    Transition probabilities between hidden states.

    Example:
    If the user was engaged last time, they are quite likely
    to still be engaged in the next 10-second window.
    """
    return {
        "disengaged": {
            "disengaged": 0.70,
            "neutral": 0.25,
            "engaged": 0.05,
        },
        "neutral": {
            "disengaged": 0.20,
            "neutral": 0.60,
            "engaged": 0.20,
        },
        "engaged": {
            "disengaged": 0.05,
            "neutral": 0.25,
            "engaged": 0.70,
        },
    }


def get_initial_probabilities() -> Dict[str, float]:
    """
    Starting probabilities when no previous state is known.
    """
    return {
        "disengaged": 0.20,
        "neutral": 0.40,
        "engaged": 0.40,
    }


def emission_scores_from_features(features: dict) -> Dict[str, float]:
    """
    Convert the current behaviour window into raw scores for each hidden state.

    These are not final probabilities yet.
    They describe how well the observed behaviour fits each state.
    """
    idle_ratio = float(features["idle_ratio"])
    scroll_speed = float(features["scroll_speed_px_s"])
    scroll_depth = float(features["scroll_depth_ratio"])
    focus_loss = float(features["focus_loss_ratio"])
    nav_rate = float(features["nav_rate_per_min"])
    interaction_rate = float(features["interaction_rate_per_min"])

    # -----------------------------
    # Disengaged evidence
    # -----------------------------
    disengaged_score = 0.0

    # High idle is a strong disengagement signal
    disengaged_score += idle_ratio * 2.0

    # High focus loss (tab switching away) is also strong
    disengaged_score += focus_loss * 2.0

    # Very low depth means little reading progress
    disengaged_score += (1.0 - scroll_depth) * 0.8

    # Very low interaction can also suggest disengagement
    disengaged_score += max(0.0, 1.0 - (interaction_rate / 5.0)) * 0.5

    # -----------------------------
    # Engaged evidence
    # -----------------------------
    engaged_score = 0.0

    # Low idle and low focus loss are good signs
    engaged_score += (1.0 - idle_ratio) * 1.2
    engaged_score += (1.0 - focus_loss) * 1.2

    # Good reading progress helps
    engaged_score += scroll_depth * 1.2

    # Moderate reading scroll speed is better than extremes
    if 5.0 <= scroll_speed <= 160.0:
        engaged_score += 0.8
    elif 160.0 < scroll_speed <= 260.0:
        engaged_score += 0.3

    # Some interaction is useful, but not too much
    if 0.5 <= interaction_rate <= 5.0:
        engaged_score += 0.5

    # Too much navigation can hurt engaged score
    if nav_rate > 6.0:
        engaged_score -= 0.3

    # -----------------------------
    # Neutral evidence
    # -----------------------------
    # Neutral is strongest when neither engaged nor disengaged dominates
    neutral_score = 1.0

    # If values are moderate, increase neutral score
    if 0.20 <= idle_ratio <= 0.60:
        neutral_score += 0.4
    if 0.05 <= focus_loss <= 0.30:
        neutral_score += 0.4
    if 0.10 <= scroll_depth <= 0.60:
        neutral_score += 0.4
    if 0.5 <= interaction_rate <= 2.5:
        neutral_score += 0.2

    raw_scores = {
        "disengaged": max(0.01, disengaged_score),
        "neutral": max(0.01, neutral_score),
        "engaged": max(0.01, engaged_score),
    }

    return normalise(raw_scores)


def apply_hmm_step(
    previous_probabilities: Dict[str, float],
    emission_probabilities: Dict[str, float],
) -> Dict[str, float]:
    """
    Perform one HMM filtering step.

    new_prob(state) =
        emission_prob(state) *
        sum(previous_prob(old_state) * transition(old_state -> state))
    """
    transitions = get_transition_matrix()
    new_probabilities: Dict[str, float] = {}

    for current_state in STATES:
        predicted_from_previous = 0.0

        for previous_state in STATES:
            predicted_from_previous += (
                previous_probabilities[previous_state]
                * transitions[previous_state][current_state]
            )

        new_probabilities[current_state] = (
            emission_probabilities[current_state] * predicted_from_previous
        )

    return normalise(new_probabilities)


def label_from_probabilities(probabilities: Dict[str, float]) -> str:
    """Return the state with the highest probability."""
    return max(probabilities, key=probabilities.get)


def score_from_label_probabilities(probabilities: Dict[str, float]) -> float:
    """
    Convert the state probabilities into a single 0-1 engagement score.

    We map:
    disengaged -> 0.0
    neutral    -> 0.5
    engaged    -> 1.0
    """
    score = (
        probabilities["disengaged"] * 0.0
        + probabilities["neutral"] * 0.5
        + probabilities["engaged"] * 1.0
    )
    return clamp_0_1(score)


def predict_engagement(
    features: dict,
    previous_state_data: dict | None = None,
) -> dict:
    """
    Predict engagement using a simple HMM-style model.

    Args:
        features: current behaviour window
        previous_state_data: previous HMM probabilities from the last window,
                             for example:
                             {
                                 "disengaged": 0.1,
                                 "neutral": 0.3,
                                 "engaged": 0.6
                             }

    Returns:
        {
            "score": float,
            "label": str,
            "state_probabilities": {...}
        }
    """
    emission_probabilities = emission_scores_from_features(features)

    if previous_state_data is None:
        previous_state_data = get_initial_probabilities()

    state_probabilities = apply_hmm_step(
        previous_probabilities=previous_state_data,
        emission_probabilities=emission_probabilities,
    )

    label = label_from_probabilities(state_probabilities)
    score = score_from_label_probabilities(state_probabilities)

    return {
        "score": score,
        "label": label,
        "state_probabilities": state_probabilities,
    }