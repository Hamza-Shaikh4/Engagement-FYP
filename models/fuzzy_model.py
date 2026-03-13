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
    idle_ratio = features["idle_ratio"]
    scroll_speed = features["scroll_speed_px_s"]
    scroll_depth = features["scroll_depth_ratio"]
    focus_loss = features["focus_loss_ratio"]
    nav_rate = features["nav_rate_per_min"]
    interaction_rate = features["interaction_rate_per_min"]

    active_ratio = 1.0 - idle_ratio

    # Membership values
    idle_high = trapezoid(idle_ratio, 0.35, 0.55, 1.0, 1.01)
    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    speed_reading = triangle(scroll_speed, 5.0, 30.0, 160.0)
    nav_high = trapezoid(nav_rate, 4.0, 7.0, 60.0, 60.01)
    interaction_ok = triangle(interaction_rate, 0.5, 2.0, 5.0)

    focus_loss_high = trapezoid(focus_loss, 0.20, 0.35, 1.0, 1.01)

    depth_good = trapezoid(scroll_depth, 0.10, 0.25, 1.0, 1.01)
    depth_low = trapezoid(scroll_depth, 0.00, 0.00, 0.08, 0.15)

    # Evidence for disengagement
    disengaged = max(
        idle_high,
        focus_loss_high,
        min(depth_low, (1.0 - active_high)),
    )

    # Evidence for engagement
    engaged = max(
        min(active_high, speed_reading),
        min(active_high, interaction_ok),
        min(active_high, depth_good),
    )

    # Reduce engagement score if user navigates too much or leaves the tab
    engaged = engaged * (1.0 - 0.3 * nav_high)
    engaged = engaged * (1.0 - 0.6 * focus_loss_high)

    total = engaged + disengaged
    score = 0.5 if total == 0.0 else engaged / total
    score = clamp_0_1(score)

    if score < 0.4:
        label = "disengaged"
    elif score < 0.7:
        label = "neutral"
    else:
        label = "engaged"

    return {"score": score, "label": label}