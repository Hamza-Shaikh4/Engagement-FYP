"""This file predicts engagement with the fuzzy model."""

# Return the trapezoid membership value
def trapezoid(value: float, a: float, b: float, c: float, d: float) -> float:
    if value <= a or value >= d:
        return 0.0
    if b <= value <= c:
        return 1.0
    if a < value < b:
        return (value - a) / (b - a)
    return (d - value) / (d - c)

# Return the triangle membership value
def triangle(value: float, a: float, b: float, c: float) -> float:
    if value <= a or value >= c:
        return 0.0
    if value == b:
        return 1.0
    if a < value < b:
        return (value - a) / (b - a)
    return (c - value) / (c - b)

# Keep a score inside the range 0 to 1.
def clamp_0_1(value: float) -> float:
    return max(0.0, min(1.0, value))

# Predict engagement using fuzzy logic.
def predict_engagement(features: dict) -> dict:

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

    active_ratio = 1.0 - idle_ratio

    # -----------------------------
    # Core memberships
    # -----------------------------
    idle_high = trapezoid(idle_ratio, 0.45, 0.65, 1.0, 1.01)
    idle_mid = triangle(idle_ratio, 0.10, 0.28, 0.50)

    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    focus_loss_high = trapezoid(focus_loss, 0.18, 0.35, 1.0, 1.01)
    focus_loss_mid = triangle(focus_loss, 0.05, 0.15, 0.30)

    depth_good = trapezoid(scroll_depth, 0.12, 0.25, 1.0, 1.01)
    depth_low = trapezoid(scroll_depth, 0.00, 0.00, 0.08, 0.15)

    interaction_ok = triangle(interaction_rate, 0.2, 1.5, 4.0)
    interaction_too_high = trapezoid(interaction_rate, 8.0, 12.0, 60.0, 60.01)

    nav_high = trapezoid(nav_rate, 4.0, 7.0, 60.0, 60.01)

    # -----------------------------
    # Reading-speed memberships
    # -----------------------------
    speed_reading = triangle(scroll_speed, 5.0, 35.0, 80.0)
    speed_mid = triangle(scroll_speed, 45.0, 75.0, 110.0)
    speed_fast = trapezoid(scroll_speed, 70.0, 90.0, 500.0, 500.01)

    # -----------------------------
    # Newer feature memberships
    # -----------------------------
    active_reading_high = trapezoid(active_reading_ratio, 0.50, 0.70, 1.0, 1.01)
    active_reading_low = trapezoid(active_reading_ratio, 0.00, 0.00, 0.25, 0.45)

    # 1–2 bursts are often neutral section-jumps, 3+ gets suspicious
    burst_some = triangle(fast_scroll_bursts, 0.0, 1.5, 3.0)
    burst_high = trapezoid(fast_scroll_bursts, 3.0, 4.0, 20.0, 20.01)

    pace_good = trapezoid(progress_rate_ratio, 0.03, 0.08, 0.40, 0.60)
    pace_fast = trapezoid(progress_rate_ratio, 0.55, 0.75, 5.0, 5.01)

    ahead_small = trapezoid(ahead_of_expected_ratio, 0.10, 0.18, 0.28, 0.38)
    ahead_large = trapezoid(ahead_of_expected_ratio, 0.35, 0.50, 2.0, 2.01)

    # -----------------------------
    # Evidence for disengagement
    # -----------------------------
    disengaged = max(
        focus_loss_high,
        min(depth_low, (1.0 - active_high)),
        speed_fast,
        burst_high,
        active_reading_low,
        pace_fast,
        ahead_large,
        min(ahead_large, burst_some),
        min(ahead_large, speed_mid),
    )

    # Idle is supportive, not dominant on its own
    disengaged = max(disengaged, idle_high * 0.55)

    # -----------------------------
    # Evidence for engagement
    # -----------------------------
    engaged = max(
        min(active_high, speed_reading),
        min(active_high, interaction_ok),
        min(active_high, depth_good),
        min(active_reading_high, pace_good),
        min(active_reading_high, depth_good),
    )

    # -----------------------------
    # Evidence for neutral
    # -----------------------------
    neutral = max(
        burst_some,
        min(active_high, speed_mid),
        min(active_ratio, pace_fast),
        min(interaction_ok, depth_good),
        ahead_small,
        idle_mid,
        focus_loss_mid,
    )

    # -----------------------------
    # Penalties and refinements
    # -----------------------------
    engaged = engaged * (1.0 - 0.25 * nav_high)
    engaged = engaged * (1.0 - 0.60 * focus_loss_high)
    engaged = engaged * (1.0 - 0.20 * interaction_too_high)
    engaged = engaged * (1.0 - 0.35 * speed_fast)
    engaged = engaged * (1.0 - 0.25 * burst_high)
    engaged = engaged * (1.0 - 0.35 * ahead_large)

    disengaged = max(disengaged, min(ahead_large, burst_high))
    disengaged = max(disengaged, min(ahead_large, speed_fast))

    # -----------------------------
    # Score calculation
    # -----------------------------
    total = engaged + neutral + disengaged

    if total == 0.0:
        score = 0.5
    else:
        score = ((engaged * 1.0) + (neutral * 0.5) + (disengaged * 0.0)) / total

    score = clamp_0_1(score)

    if score < 0.4:
        label = "disengaged"
    elif score < 0.7:
        label = "neutral"
    else:
        label = "engaged"

    return {"score": score, "label": label}