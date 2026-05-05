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
            "disengaged": 0.64,
            "neutral": 0.30,
            "engaged": 0.06,
        },
        "neutral": {
            "disengaged": 0.08,
            "neutral": 0.76,
            "engaged": 0.16,
        },
        "engaged": {
            "disengaged": 0.03,
            "neutral": 0.13,
            "engaged": 0.84,
        },
    }


def get_initial_probabilities() -> Dict[str, float]:
    return {
        "disengaged": 0.20,
        "neutral": 0.45,
        "engaged": 0.35,
    }


def get_progress_band(scroll_depth: float) -> str:
    if scroll_depth < 0.35:
        return "early"
    if scroll_depth < 0.75:
        return "middle"
    return "late"


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

    progress_band = get_progress_band(scroll_depth)

    # Pace softening by book progress
    # Early: stricter against rushing
    # Middle: balanced
    # Late: more tolerant because readers reposition more
    if progress_band == "early":
        ahead_multiplier = 1.15
        progress_multiplier = 1.00
    elif progress_band == "middle":
        ahead_multiplier = 1.00
        progress_multiplier = 0.95
    else:
        ahead_multiplier = 0.65
        progress_multiplier = 0.70

    disengaged_score = 0.0

    # Strongest disengagement evidence
    disengaged_score += focus_loss * 2.15

    # Idle matters on its own when severe — a user who has left the page
    # entirely will have both high idle AND high focus_loss, but even idle
    # alone at ≥0.70 is a meaningful signal.
    if focus_loss > 0.10:
        disengaged_score += idle_ratio * 1.20   # was 0.90 — stronger when tab also hidden
    elif idle_ratio >= 0.70:
        disengaged_score += idle_ratio * 0.55   # was 0.18 — moderate signal for pure idle
    else:
        disengaged_score += idle_ratio * 0.18

    disengaged_score += (1.0 - scroll_depth) * 0.05

    # Average speed
    if scroll_speed > 95.0:
        disengaged_score += 1.00
    elif scroll_speed > 75.0:
        disengaged_score += 0.55
    elif scroll_speed > 55.0:
        disengaged_score += 0.20

    # Bursts:
    # 1–2 = mostly harmless
    # 3–4 = suspicious only with support
    # 5+ = strong skim evidence
    if fast_scroll_bursts >= 5:
        disengaged_score += 1.25
    elif fast_scroll_bursts >= 4:
        disengaged_score += 0.75
    elif fast_scroll_bursts >= 3:
        disengaged_score += 0.25
    elif fast_scroll_bursts >= 2:
        disengaged_score += 0.08
    elif fast_scroll_bursts >= 1:
        disengaged_score += 0.02

    # Page progress within the current window
    if progress_rate_ratio >= 0.75:
        disengaged_score += 0.85 * progress_multiplier
    elif progress_rate_ratio >= 0.55:
        disengaged_score += 0.35 * progress_multiplier
    elif progress_rate_ratio >= 0.35:
        disengaged_score += 0.10 * progress_multiplier

    # Ahead of expected reading pace
    if ahead_of_expected_ratio >= 0.70:
        disengaged_score += 1.20 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.50:
        disengaged_score += 0.75 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.30:
        disengaged_score += 0.22 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.15:
        disengaged_score += 0.05 * ahead_multiplier

    # Explicit skimming signature:
    # only strongly punish when multiple suspicious cues happen together
    skim_signals = 0
    if scroll_speed > 70.0:
        skim_signals += 1
    if fast_scroll_bursts >= 3:
        skim_signals += 1
    if ahead_of_expected_ratio >= 0.25:
        skim_signals += 1
    if active_reading_ratio < 0.45:
        skim_signals += 1
    if progress_rate_ratio >= 0.45:
        skim_signals += 1

    if skim_signals >= 4:
        disengaged_score += 1.00
    elif skim_signals == 3:
        disengaged_score += 0.55
    elif skim_signals == 2:
        disengaged_score += 0.20

    # Combined rules
    if scroll_speed > 55.0 and fast_scroll_bursts >= 4:
        disengaged_score += 0.55

    if scroll_speed > 55.0 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.40 * ahead_multiplier

    if scroll_speed > 75.0 and fast_scroll_bursts >= 3 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.85 * ahead_multiplier

    if ahead_of_expected_ratio >= 0.35 and fast_scroll_bursts >= 4:
        disengaged_score += 0.55 * ahead_multiplier

    if focus_loss >= 0.20 and ahead_of_expected_ratio >= 0.25:
        disengaged_score += 0.50 * ahead_multiplier

    if focus_loss >= 0.20 and fast_scroll_bursts >= 3:
        disengaged_score += 0.40

    # Low active_reading_ratio is suspicious — but protect genuinely slow readers
    # who scroll slowly and stay focused (slow speed = deliberate reading, not absence).
    slow_reader_protected = scroll_speed <= 45.0 and idle_ratio < 0.55
    if not slow_reader_protected:
        if active_reading_ratio < 0.20:
            disengaged_score += 0.30
        elif active_reading_ratio < 0.40:
            disengaged_score += 0.10

    if nav_rate > 8.0:
        disengaged_score += 0.12

    engaged_score = 0.0

    engaged_score += (1.0 - idle_ratio) * 0.95
    engaged_score += (1.0 - focus_loss) * 1.20
    engaged_score += scroll_depth * 0.92

    if 5.0 <= scroll_speed <= 45.0:
        engaged_score += 0.95
        if idle_ratio < 0.40 and focus_loss < 0.15:
            engaged_score += 0.35
    elif 45.0 < scroll_speed <= 65.0:
        engaged_score += 0.38
    elif 65.0 < scroll_speed <= 85.0:
        engaged_score += 0.10

    if 0.2 <= interaction_rate <= 4.0:
        engaged_score += 0.18

    if active_reading_ratio >= 0.75:
        engaged_score += 0.72
    elif active_reading_ratio >= 0.55:
        engaged_score += 0.30

    if fast_scroll_bursts == 0:
        engaged_score += 0.12
    elif fast_scroll_bursts >= 5:
        engaged_score -= 0.90
    elif fast_scroll_bursts >= 4:
        engaged_score -= 0.60
    elif fast_scroll_bursts >= 3:
        engaged_score -= 0.22
    elif fast_scroll_bursts >= 2:
        engaged_score -= 0.05

    if scroll_speed > 55.0:
        engaged_score -= 0.10
    if scroll_speed > 75.0:
        engaged_score -= 0.22
    if scroll_speed > 95.0:
        engaged_score -= 0.40

    if progress_rate_ratio >= 0.75:
        engaged_score -= 0.35 * progress_multiplier
    elif progress_rate_ratio >= 0.55:
        engaged_score -= 0.14 * progress_multiplier

    if ahead_of_expected_ratio >= 0.70:
        engaged_score -= 0.90 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.50:
        engaged_score -= 0.45 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.30:
        engaged_score -= 0.12 * ahead_multiplier
    elif ahead_of_expected_ratio >= 0.15:
        engaged_score -= 0.03 * ahead_multiplier

    if focus_loss > 0.35:
        engaged_score -= 0.55

    neutral_score = 1.0

    # Strengthen neutral as a proper middle state
    if 0.15 <= idle_ratio <= 0.70:
        neutral_score += 0.45
    if 0.00 <= focus_loss <= 0.15:
        neutral_score += 0.28
    if 0.10 <= scroll_depth <= 0.85:
        neutral_score += 0.20
    if 0.1 <= interaction_rate <= 2.0:
        neutral_score += 0.18
    if 45.0 < scroll_speed <= 90.0:
        neutral_score += 0.60
    if 0.35 <= active_reading_ratio <= 0.75:
        neutral_score += 0.30

    if fast_scroll_bursts == 1:
        neutral_score += 0.35
    elif fast_scroll_bursts == 2:
        neutral_score += 0.30
    elif fast_scroll_bursts == 3:
        neutral_score += 0.18

    if 0.20 <= progress_rate_ratio <= 0.55:
        neutral_score += 0.24

    if 0.10 <= ahead_of_expected_ratio <= 0.35:
        neutral_score += 0.28

    raw_scores = {
        "disengaged": max(0.01, disengaged_score),
        "neutral": max(0.01, neutral_score),
        "engaged": max(0.01, engaged_score),
    }

    probabilities = normalise(raw_scores)

    # Hard cap only for clear skim patterns
    if (
        ahead_of_expected_ratio >= 0.75
        or fast_scroll_bursts >= 5
        or (scroll_speed > 75.0 and fast_scroll_bursts >= 4 and ahead_of_expected_ratio >= 0.25)
        or (focus_loss >= 0.30 and ahead_of_expected_ratio >= 0.30)
    ):
        probabilities["engaged"] = min(probabilities["engaged"], 0.10)
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

    idle_ratio = float(features.get("idle_ratio", 0.0))
    focus_loss = float(features.get("focus_loss_ratio", 0.0))
    ahead_of_expected_ratio = float(features.get("ahead_of_expected_ratio", 0.0))
    fast_scroll_bursts = float(features.get("fast_scroll_bursts", 0))
    active_reading_ratio = float(features.get("active_reading_ratio", 0.5))
    scroll_speed = float(features.get("scroll_speed_px_s", 0.0))

    # Track repeated full-idle windows.
    # A single pause-heavy window should not be punished.
    previous_idle_streak = int(previous_state_data.get("_idle_streak_windows", 0))

    if idle_ratio > 0.95:
        idle_streak = previous_idle_streak + 1
    else:
        idle_streak = 0

    # Recovery rule:
    # faster recovery after cleaner windows.
    # Do not recover while the user is in a full-idle streak.
    if (
        idle_streak == 0
        and focus_loss < 0.10
        and ahead_of_expected_ratio < 0.18
        and fast_scroll_bursts <= 1
        and active_reading_ratio >= 0.55
        and scroll_speed <= 65.0
    ):
        state_probabilities["neutral"] += 0.05
        state_probabilities["engaged"] += 0.03
        state_probabilities["disengaged"] = max(
            0.001,
            state_probabilities["disengaged"] - 0.08,
        )
        state_probabilities = normalise(state_probabilities)

    # Consecutive idle rule:
    # 1st full-idle window: do nothing, may be a reading/thinking pause.
    # 2nd full-idle window: start lowering engagement lightly.
    # 3rd+ full-idle window: increasingly lower engagement each window.
    if idle_streak >= 2:
        idle_pressure = min(
            0.30,
            0.08 + ((idle_streak - 2) * 0.07),
        )

        state_probabilities["disengaged"] += idle_pressure
        state_probabilities["neutral"] += idle_pressure * 0.40
        state_probabilities["engaged"] -= idle_pressure

        state_probabilities["engaged"] = max(
            0.001,
            state_probabilities["engaged"],
        )

        state_probabilities = normalise(state_probabilities)

    if (
        ahead_of_expected_ratio >= 0.75
        or fast_scroll_bursts >= 5
        or (focus_loss >= 0.35 and ahead_of_expected_ratio >= 0.35)
    ):
        state_probabilities["engaged"] = min(state_probabilities["engaged"], 0.10)
        state_probabilities = normalise(state_probabilities)

    label = label_from_probabilities(state_probabilities)
    score = score_from_label_probabilities(state_probabilities)

    # Store idle streak inside the HMM state data so the next window can use it.
    # The HMM transition step only reads "disengaged", "neutral", and "engaged",
    # so this extra key will not interfere with the transition calculation.
    state_probabilities["_idle_streak_windows"] = idle_streak

    return {
        "score": score,
        "label": label,
        "state_probabilities": state_probabilities,
    }