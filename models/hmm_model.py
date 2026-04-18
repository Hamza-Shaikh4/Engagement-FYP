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
            "disengaged": 0.68,
            "neutral": 0.26,
            "engaged": 0.06,
        },
        "neutral": {
            "disengaged": 0.08,
            "neutral": 0.78,
            "engaged": 0.14,
        },
        "engaged": {
            "disengaged": 0.03,
            "neutral": 0.14,
            "engaged": 0.83,
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
    progress_rate_ratio = float(features.get("progress_rate_ratio", 0.0))
    ahead_of_expected_ratio = float(features.get("ahead_of_expected_ratio", 0.0))

    disengaged_score = 0.0

    # Strongest disengagement evidence
    disengaged_score += focus_loss * 2.2

    # Idle matters, but should not dominate on its own
    if focus_loss > 0.10:
        disengaged_score += idle_ratio * 1.0
    else:
        disengaged_score += idle_ratio * 0.20

    disengaged_score += (1.0 - scroll_depth) * 0.06

    # Average speed across the whole window
    if scroll_speed > 90.0:
        disengaged_score += 1.00
    elif scroll_speed > 70.0:
        disengaged_score += 0.55
    elif scroll_speed > 50.0:
        disengaged_score += 0.20

    # Bursts: 2 is not strong enough on its own
    if fast_scroll_bursts >= 5:
        disengaged_score += 1.35
    elif fast_scroll_bursts >= 4:
        disengaged_score += 1.00
    elif fast_scroll_bursts >= 3:
        disengaged_score += 0.65
    elif fast_scroll_bursts >= 2:
        disengaged_score += 0.18
    elif fast_scroll_bursts >= 1:
        disengaged_score += 0.03

    # Progress through the page in a single window
    if progress_rate_ratio >= 0.70:
        disengaged_score += 0.90
    elif progress_rate_ratio >= 0.50:
        disengaged_score += 0.40
    elif progress_rate_ratio >= 0.35:
        disengaged_score += 0.15

    # Ahead of expected reading pace for this book
    if ahead_of_expected_ratio >= 0.70:
        disengaged_score += 1.35
    elif ahead_of_expected_ratio >= 0.50:
        disengaged_score += 0.85
    elif ahead_of_expected_ratio >= 0.30:
        disengaged_score += 0.30
    elif ahead_of_expected_ratio >= 0.15:
        disengaged_score += 0.08

    # Combined skim patterns
    if scroll_speed > 50.0 and fast_scroll_bursts >= 3:
        disengaged_score += 0.55

    if scroll_speed > 50.0 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.45

    if scroll_speed > 70.0 and fast_scroll_bursts >= 3 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.90

    if ahead_of_expected_ratio >= 0.35 and fast_scroll_bursts >= 3:
        disengaged_score += 0.60

    if focus_loss >= 0.20 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.55

    if focus_loss >= 0.20 and fast_scroll_bursts >= 3:
        disengaged_score += 0.45

    if active_reading_ratio < 0.20:
        disengaged_score += 0.35
    elif active_reading_ratio < 0.40:
        disengaged_score += 0.12

    if nav_rate > 8.0:
        disengaged_score += 0.15

    engaged_score = 0.0

    engaged_score += (1.0 - idle_ratio) * 0.95
    engaged_score += (1.0 - focus_loss) * 1.20
    engaged_score += scroll_depth * 0.90

    if 5.0 <= scroll_speed <= 45.0:
        engaged_score += 0.95
    elif 45.0 < scroll_speed <= 65.0:
        engaged_score += 0.38
    elif 65.0 < scroll_speed <= 85.0:
        engaged_score += 0.10

    if 0.2 <= interaction_rate <= 4.0:
        engaged_score += 0.18

    if active_reading_ratio >= 0.75:
        engaged_score += 0.70
    elif active_reading_ratio >= 0.55:
        engaged_score += 0.30

    if fast_scroll_bursts == 0:
        engaged_score += 0.12
    elif fast_scroll_bursts >= 5:
        engaged_score -= 0.85
    elif fast_scroll_bursts >= 4:
        engaged_score -= 0.60
    elif fast_scroll_bursts >= 3:
        engaged_score -= 0.35
    elif fast_scroll_bursts >= 2:
        engaged_score -= 0.08

    if scroll_speed > 50.0:
        engaged_score -= 0.12
    if scroll_speed > 70.0:
        engaged_score -= 0.25
    if scroll_speed > 90.0:
        engaged_score -= 0.45

    if progress_rate_ratio >= 0.70:
        engaged_score -= 0.40
    elif progress_rate_ratio >= 0.50:
        engaged_score -= 0.18

    if ahead_of_expected_ratio >= 0.70:
        engaged_score -= 0.95
    elif ahead_of_expected_ratio >= 0.50:
        engaged_score -= 0.50
    elif ahead_of_expected_ratio >= 0.30:
        engaged_score -= 0.15
    elif ahead_of_expected_ratio >= 0.15:
        engaged_score -= 0.04

    if focus_loss > 0.35:
        engaged_score -= 0.60

    neutral_score = 1.0

    if 0.15 <= idle_ratio <= 0.70:
        neutral_score += 0.45
    if 0.00 <= focus_loss <= 0.15:
        neutral_score += 0.25
    if 0.10 <= scroll_depth <= 0.85:
        neutral_score += 0.22
    if 0.1 <= interaction_rate <= 2.0:
        neutral_score += 0.18
    if 45.0 < scroll_speed <= 90.0:
        neutral_score += 0.55
    if 0.35 <= active_reading_ratio <= 0.75:
        neutral_score += 0.28

    if fast_scroll_bursts == 1:
        neutral_score += 0.35
    elif fast_scroll_bursts == 2:
        neutral_score += 0.28

    if 0.20 <= progress_rate_ratio <= 0.55:
        neutral_score += 0.22

    if 0.10 <= ahead_of_expected_ratio <= 0.35:
        neutral_score += 0.22

    raw_scores = {
        "disengaged": max(0.01, disengaged_score),
        "neutral": max(0.01, neutral_score),
        "engaged": max(0.01, engaged_score),
    }

    probabilities = normalise(raw_scores)

    # Strong disengagement override only for clear skim patterns
    if (
        ahead_of_expected_ratio >= 0.70
        or fast_scroll_bursts >= 5
        or (scroll_speed > 70.0 and fast_scroll_bursts >= 3 and ahead_of_expected_ratio >= 0.25)
        or (focus_loss >= 0.30 and ahead_of_expected_ratio >= 0.30)
    ):
        probabilities["engaged"] = min(probabilities["engaged"], 0.12)
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

    focus_loss = float(features.get("focus_loss_ratio", 0.0))
    ahead_of_expected_ratio = float(features.get("ahead_of_expected_ratio", 0.0))
    fast_scroll_bursts = float(features.get("fast_scroll_bursts", 0))
    active_reading_ratio = float(features.get("active_reading_ratio", 0.5))

    # Recovery rule
    if (
        focus_loss < 0.10
        and ahead_of_expected_ratio < 0.20
        and fast_scroll_bursts <= 1
        and active_reading_ratio >= 0.55
    ):
        state_probabilities["neutral"] += 0.05
        state_probabilities["engaged"] += 0.02
        state_probabilities["disengaged"] -= 0.07
        state_probabilities = normalise(state_probabilities)

    # Clear skim override
    if (
        ahead_of_expected_ratio >= 0.70
        or fast_scroll_bursts >= 5
        or (focus_loss >= 0.30 and ahead_of_expected_ratio >= 0.30)
    ):
        state_probabilities["engaged"] = min(state_probabilities["engaged"], 0.12)
        state_probabilities = normalise(state_probabilities)

    label = label_from_probabilities(state_probabilities)
    score = score_from_label_probabilities(state_probabilities)

    return {
        "score": score,
        "label": label,
        "state_probabilities": state_probabilities,
    }