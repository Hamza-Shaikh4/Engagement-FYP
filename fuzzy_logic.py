def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)


def triangle(x: float, a: float, b: float, c: float) -> float:
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def clamp_0_1(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def fuzzy_engagement(
    idle_ratio: float,
    scroll_speed_px_s: float,
    scroll_depth_ratio: float,
    focus_loss_ratio: float,
    nav_rate_per_min: float,
    interaction_rate_per_min: float,
):
    """
    Output:
      score in [0..1] and label: disengaged / neutral / engaged

    Design intent:
    - avoid punishing slow readers
    - focus loss (tab away) is a strong disengagement signal
    - depth progress helps, but low depth doesn't automatically mean disengaged
    """

    active_ratio = 1.0 - idle_ratio

    # Idle / Active
    idle_high = trapezoid(idle_ratio, 0.35, 0.55, 1.0, 1.01)
    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    # Scroll speed: allow "reading movement"
    speed_reading = triangle(scroll_speed_px_s, 5.0, 30.0, 160.0)

    # Navigation & interaction
    nav_high = trapezoid(nav_rate_per_min, 4.0, 7.0, 60.0, 60.01)
    interaction_ok = triangle(interaction_rate_per_min, 0.5, 2.0, 5.0)

    # Focus loss (tab switching)
    focus_loss_high = trapezoid(focus_loss_ratio, 0.20, 0.35, 1.0, 1.01)

    # Depth progress
    depth_good = trapezoid(scroll_depth_ratio, 0.10, 0.25, 1.0, 1.01)
    depth_low = trapezoid(scroll_depth_ratio, 0.00, 0.00, 0.08, 0.15)

    # Disengaged evidence
    disengaged_idle = idle_high
    disengaged_focus = focus_loss_high
    disengaged_stuck = min(depth_low, (1.0 - active_high))
    disengaged = max(disengaged_idle, disengaged_focus, disengaged_stuck)

    # Engaged evidence
    engaged_reading = min(active_high, speed_reading)
    engaged_interaction = min(active_high, interaction_ok)
    engaged_progress = min(active_high, depth_good)
    engaged = max(engaged_reading, engaged_interaction, engaged_progress)

    # Penalise "busy navigation" a bit (distraction) and focus loss a lot
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

    return score, label