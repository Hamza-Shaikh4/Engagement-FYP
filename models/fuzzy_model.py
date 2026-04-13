def trapezoid(value: float, a: float, b: float, c: float, d: float) -> float:
    """Return trapezoid membership value."""
    if value <= a or value >= d:
        return 0.0
    if b <= value <= c:
        return 1.0
    if a < value < b:
        return (value - a) / (b - a)
    return (d - value) / (d - c)


def triangle(value: float, a: float, b: float, c: float) -> float:
    """Return triangle membership value."""
    if value <= a or value >= c:
        return 0.0
    if value == b:
        return 1.0
    if a < value < b:
        return (value - a) / (b - a)
    return (c - value) / (c - b)


def clamp_0_1(value: float) -> float:
    """Keep a score inside the range 0 to 1."""
    return max(0.0, min(1.0, value))


def predict_engagement(features: dict) -> dict:
    """
    Predict engagement using fuzzy logic.

    Returns:
        {
            "score": float between 0 and 1,
            "label": "engaged" | "neutral" | "disengaged"
        }
    """
    idle_ratio = float(features["idle_ratio"])
    scroll_speed = float(features["scroll_speed_px_s"])
    scroll_depth = float(features["scroll_depth_ratio"])
    focus_loss = float(features["focus_loss_ratio"])
    nav_rate = float(features["nav_rate_per_min"])
    interaction_rate = float(features["interaction_rate_per_min"])

    # New optional features, while keeping old names unchanged
    fast_scroll_bursts = float(features.get("fast_scroll_bursts", 0))
    active_reading_ratio = float(features.get("active_reading_ratio", 0.5))
    progress_rate_ratio = float(features.get("progress_rate_ratio", 0.5))

    active_ratio = 1.0 - idle_ratio

    # -----------------------------
    # Original memberships
    # -----------------------------
    idle_high = trapezoid(idle_ratio, 0.35, 0.55, 1.0, 1.01)
    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    # Refined scroll speed memberships
    speed_reading = triangle(scroll_speed, 5.0, 35.0, 140.0)
    speed_fast = trapezoid(scroll_speed, 150.0, 220.0, 500.0, 500.01)

    nav_high = trapezoid(nav_rate, 4.0, 7.0, 60.0, 60.01)
    interaction_ok = triangle(interaction_rate, 0.5, 2.0, 5.0)
    interaction_too_high = trapezoid(interaction_rate, 8.0, 12.0, 60.0, 60.01)

    focus_loss_high = trapezoid(focus_loss, 0.20, 0.35, 1.0, 1.01)

    depth_good = trapezoid(scroll_depth, 0.10, 0.25, 1.0, 1.01)
    depth_low = trapezoid(scroll_depth, 0.00, 0.00, 0.08, 0.15)

    # -----------------------------
    # New memberships
    # -----------------------------
    active_reading_high = trapezoid(active_reading_ratio, 0.50, 0.70, 1.0, 1.01)
    active_reading_low = trapezoid(active_reading_ratio, 0.00, 0.00, 0.25, 0.45)

    burst_high = trapezoid(fast_scroll_bursts, 2.0, 4.0, 20.0, 20.01)
    burst_some = triangle(fast_scroll_bursts, 0.0, 1.0, 3.0)

    pace_good = trapezoid(progress_rate_ratio, 0.03, 0.08, 0.45, 0.65)
    pace_fast = trapezoid(progress_rate_ratio, 0.70, 1.00, 5.0, 5.01)

    # -----------------------------
    # Evidence for disengagement
    # -----------------------------
    disengaged = max(
        idle_high,
        focus_loss_high,
        min(depth_low, (1.0 - active_high)),
        speed_fast,
        burst_high,
        active_reading_low,
        pace_fast,
    )

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
        min(active_high, speed_fast),
        min(active_ratio, pace_fast),
        min(interaction_ok, depth_good),
    )

    # -----------------------------
    # Penalties and refinements
    # -----------------------------
    # Too much navigation or focus loss weakens strong engagement
    engaged = engaged * (1.0 - 0.30 * nav_high)
    engaged = engaged * (1.0 - 0.60 * focus_loss_high)

    # Very high interaction can be restless rather than engaged
    engaged = engaged * (1.0 - 0.25 * interaction_too_high)

    # Strong fast-scroll evidence also suppresses engagement
    engaged = engaged * (1.0 - 0.50 * speed_fast)
    engaged = engaged * (1.0 - 0.40 * burst_high)

    # -----------------------------
    # Score calculation
    # -----------------------------
    # Use all three states instead of only engaged/disengaged
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