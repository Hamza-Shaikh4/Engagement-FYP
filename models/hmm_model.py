# models/hmm_model.py

from typing import Dict

STATES = ["disengaged", "neutral", "engaged"]


def clamp_0_1(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalise(probabilities: Dict[str, float]) -> Dict[str, float]:
    total = sum(probabilities.values())

    if total <= 0:
        equal = 1.0 / len(probabilities)
        return {state: equal for state in probabilities}

    return {state: value / total for state, value in probabilities.items()}


def get_transition_matrix() -> Dict[str, Dict[str, float]]:
    return {
        "disengaged": {
            "disengaged": 0.72,
            "neutral": 0.22,
            "engaged": 0.06,
        },
        "neutral": {
            "disengaged": 0.18,
            "neutral": 0.64,
            "engaged": 0.18,
        },
        "engaged": {
            "disengaged": 0.06,
            "neutral": 0.22,
            "engaged": 0.72,
        },
    }


def get_initial_probabilities() -> Dict[str, float]:
    return {
        "disengaged": 0.20,
        "neutral": 0.45,
        "engaged": 0.35,
    }


def emission_scores_from_features(features: dict) -> Dict[str, float]:
    idle_ratio = float(features["idle_ratio"])
    scroll_speed = float(features["scroll_speed_px_s"])
    scroll_depth = float(features["scroll_depth_ratio"])
    focus_loss = float(features["focus_loss_ratio"])
    nav_rate = float(features["nav_rate_per_min"])
    interaction_rate = float(features["interaction_rate_per_min"])

    fast_scroll_bursts = float(features.get("fast_scroll_bursts", 0))
    active_reading_ratio = float(features.get("active_reading_ratio", 0.5))
    max_scroll_speed = float(features.get("max_scroll_speed_px_s", 0.0))

    # -----------------------------
    # Disengaged evidence
    # -----------------------------
    disengaged_score = 0.0

    disengaged_score += idle_ratio * 1.8
    disengaged_score += focus_loss * 2.0
    disengaged_score += (1.0 - scroll_depth) * 0.4

    if 220.0 < scroll_speed <= 350.0:
        disengaged_score += 0.4
    elif 350.0 < scroll_speed <= 550.0:
        disengaged_score += 0.9
    elif scroll_speed > 550.0:
        disengaged_score += 1.4

    if fast_scroll_bursts >= 5:
        disengaged_score += 1.1
    elif fast_scroll_bursts >= 3:
        disengaged_score += 0.6

    if max_scroll_speed >= 1600.0:
        disengaged_score += 2.0
    elif max_scroll_speed >= 1100.0:
        disengaged_score += 1.2
    elif max_scroll_speed >= 800.0:
        disengaged_score += 0.6

    if active_reading_ratio < 0.20:
        disengaged_score += 0.8
    elif active_reading_ratio < 0.40:
        disengaged_score += 0.3

    if nav_rate > 8.0:
        disengaged_score += 0.3

    # -----------------------------
    # Engaged evidence
    # -----------------------------
    engaged_score = 0.0

    engaged_score += (1.0 - idle_ratio) * 1.2
    engaged_score += (1.0 - focus_loss) * 1.2
    engaged_score += scroll_depth * 1.0

    if 5.0 <= scroll_speed <= 110.0:
        engaged_score += 0.9
    elif 110.0 < scroll_speed <= 180.0:
        engaged_score += 0.4
    elif 180.0 < scroll_speed <= 230.0:
        engaged_score += 0.1

    if 0.5 <= interaction_rate <= 5.0:
        engaged_score += 0.4

    if active_reading_ratio >= 0.75:
        engaged_score += 0.8
    elif active_reading_ratio >= 0.55:
        engaged_score += 0.4

    if fast_scroll_bursts == 0:
        engaged_score += 0.2
    elif fast_scroll_bursts >= 4:
        engaged_score -= 0.7

    if max_scroll_speed >= 1100.0:
        engaged_score -= 1.0
    elif max_scroll_speed >= 800.0:
        engaged_score -= 0.5

    if nav_rate > 6.0:
        engaged_score -= 0.3

    if focus_loss > 0.35:
        engaged_score -= 0.5

    # -----------------------------
    # Neutral evidence
    # -----------------------------
    neutral_score = 1.0

    if 0.15 <= idle_ratio <= 0.55:
        neutral_score += 0.4
    if 0.05 <= focus_loss <= 0.30:
        neutral_score += 0.4
    if 0.10 <= scroll_depth <= 0.60:
        neutral_score += 0.3
    if 0.5 <= interaction_rate <= 2.5:
        neutral_score += 0.2
    if 180.0 < scroll_speed <= 320.0:
        neutral_score += 0.25
    if 0.35 <= active_reading_ratio <= 0.65:
        neutral_score += 0.3
    if 1 <= fast_scroll_bursts <= 2:
        neutral_score += 0.2

    raw_scores = {
        "disengaged": max(0.01, disengaged_score),
        "neutral": max(0.01, neutral_score),
        "engaged": max(0.01, engaged_score),
    }

    probabilities = normalise(raw_scores)

    # Only hard-cap truly extreme skimming
    if fast_scroll_bursts >= 5 or max_scroll_speed >= 1600.0:
        probabilities["engaged"] = min(probabilities["engaged"], 0.15)
        probabilities = normalise(probabilities)

    return probabilities


def apply_hmm_step(
    previous_probabilities: Dict[str, float],
    emission_probabilities: Dict[str, float],
) -> Dict[str, float]:
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
    return max(probabilities, key=probabilities.get)


def score_from_label_probabilities(probabilities: Dict[str, float]) -> float:
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
    emission_probabilities = emission_scores_from_features(features)

    if previous_state_data is None:
        previous_state_data = get_initial_probabilities()

    state_probabilities = apply_hmm_step(
        previous_probabilities=previous_state_data,
        emission_probabilities=emission_probabilities,
    )

    fast_scroll_bursts = float(features.get("fast_scroll_bursts", 0))
    max_scroll_speed = float(features.get("max_scroll_speed_px_s", 0.0))

    if fast_scroll_bursts >= 5 or max_scroll_speed >= 1600.0:
        state_probabilities["engaged"] = min(state_probabilities["engaged"], 0.15)
        state_probabilities = normalise(state_probabilities)

    label = label_from_probabilities(state_probabilities)
    score = score_from_label_probabilities(state_probabilities)

    return {
        "score": score,
        "label": label,
        "state_probabilities": state_probabilities,
    }