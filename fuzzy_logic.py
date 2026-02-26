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
    scroll_depth_ratio: float,     
    focus_loss_ratio: float,       
    nav_rate_per_min: float,
    interaction_rate_per_min: float,
):
    active_ratio = 1.0 - idle_ratio

    # -------------------------
    # Membership functions
    # -------------------------

    # Idle/Active
    idle_high   = trapezoid(idle_ratio, 0.35, 0.55, 1.0, 1.01)
    active_high = trapezoid(active_ratio, 0.55, 0.75, 1.0, 1.01)

    # Scroll speed "reasonable reading movement"
    # (still allows slow readers to be considered engaged)
    speed_reading = triangle(scroll_speed_px_s, 5.0, 30.0, 160.0)

    # Navigation and interaction
    nav_high = trapezoid(nav_rate_per_min, 4.0, 7.0, 60.0, 60.01)
    int_med  = triangle(interaction_rate_per_min, 0.5, 2.0, 5.0)

    # Focus loss (tab switching / leaving page)
    # If user is away for >25% of the window, that’s strong disengagement evidence
    focus_loss_high = trapezoid(focus_loss_ratio, 0.20, 0.35, 1.0, 1.01)

    # Scroll depth progress
    # If depth is low over a window, it doesn't mean disengaged, but over time it can matter.
    # Here: "good progress" means they are moving through the content.
    depth_progress_good = trapezoid(scroll_depth_ratio, 0.10, 0.25, 1.0, 1.01)
    depth_progress_low  = trapezoid(scroll_depth_ratio, 0.00, 0.00, 0.08, 0.15)

    # -------------------------
    # Rules
    # -------------------------

    # Disengaged evidence:
    # 1) High idle is disengaged evidence
    # 2) High focus loss is very strong disengaged evidence
    # 3) Very low depth progress + not active can also add a little disengaged evidence
    disengaged_idle = idle_high
    disengaged_focus = focus_loss_high
    disengaged_stuck = min(depth_progress_low, (1.0 - active_high))

    disengaged = max(disengaged_idle, disengaged_focus, disengaged_stuck)

    # Engaged evidence:
    # 1) Active + reasonable reading scroll (even slow)
    engaged_reading = min(active_high, speed_reading)

    # 2) Active + some interaction (e.g., clicking definitions, buttons)
    engaged_interaction = min(active_high, int_med)

    # 3) Active + progressing through content (depth)
    engaged_progress = min(active_high, depth_progress_good)

    engaged = max(engaged_reading, engaged_interaction, engaged_progress)

    # Penalise engaged if lots of navigation (likely distraction)
    engaged = engaged * (1.0 - 0.3 * nav_high)

    # If focus loss is high, reduce engagement confidence
    engaged = engaged * (1.0 - 0.6 * focus_loss_high)

    # -------------------------
    # Score
    # -------------------------
    total = engaged + disengaged
    score = 0.5 if total == 0.0 else engaged / total
    score = boundary_0_to_1(score)

    # -------------------------
    # Label
    # -------------------------
    if score < 0.4:
        label = "disengaged"
    elif score < 0.7:
        label = "neutral"
    else:
        label = "engaged"

    return score, label

