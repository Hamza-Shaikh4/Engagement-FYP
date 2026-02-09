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


def boundary_0_to_1(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def fuzzy_engagement(
    idle_ratio: float,
    scroll_speed_px_s: float,
    nav_rate_per_min: float,
    interaction_rate_per_min: float,
):
    active_ratio = 1.0 - idle_ratio

    # Memberships
    idle_high   = trapezoid(idle_ratio, 0.35, 0.55, 1.0, 1.01)
    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    speed_med = triangle(scroll_speed_px_s, 10.0, 60.0, 180.0)

    nav_high = trapezoid(nav_rate_per_min, 4.0, 7.0, 60.0, 60.01)
    int_med  = triangle(interaction_rate_per_min, 0.5, 2.0, 5.0)

    # Rules
    disengaged = idle_high

    engaged_reading = min(active_high, speed_med)
    engaged_interaction = min(active_high, int_med)
    engaged = max(engaged_reading, engaged_interaction)

    engaged = engaged * (1.0 - 0.3 * nav_high)

    # Score
    total = engaged + disengaged
    score = 0.5 if total == 0.0 else engaged / total
    score = boundary_0_to_1(score)

    # Label
    if score < 0.4:
        label = "disengaged"
    elif score < 0.7:
        label = "neutral"
    else:
        label = "engaged"

    return score, label
