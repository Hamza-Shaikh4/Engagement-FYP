def how_high(value, start, end):
    # 0 if below start, 1 if above end, else gradually increases
    if value <= start:
        return 0
    if value >= end:
        return 1
    return (value - start) / (end - start)


def fuzzy_engagement(idle_ratio, scroll_speed, interaction_count):
    """
    Returns: (score, label)
    score: 0..1 where 0 is disengaged and 1 is engaged
    """

    # 1) Convert raw numbers into fuzzy "feelings" (0..1)

    idle_high = how_high(idle_ratio, start=0.3, end=0.6)     # higher idle -> more disengaged
    idle_low  = 1 - idle_high

    # scroll "good" for reading (you can tune these later)
    scroll_good = how_high(scroll_speed, start=50, end=150)  # becomes "good" as speed rises
    scroll_too_fast = how_high(scroll_speed, start=250, end=500)  # too fast -> skimming

    interaction_some = how_high(interaction_count, start=1, end=5)

    # 2) Rules

    # Disengaged rule: if idle is high, disengaged is strong
    disengaged_strength = idle_high

    # Engaged rules: scrolling looks like reading OR they interact a bit
    engaged_strength = max(scroll_good, interaction_some)

    # If they are skimming very fast, reduce engagement a bit
    engaged_strength = engaged_strength * (1 - scroll_too_fast)

    # If idle is low, that supports engagement
    engaged_strength = min(engaged_strength, idle_low + 0.2)  # +0.2 makes it less strict

    # 3) Combine engaged + disengaged into one score
    # If disengaged is strong, score should go down.
    # If engaged is strong, score should go up.

    total = engaged_strength + disengaged_strength

    if total == 0:
        score = 0.5  # no info => neutral
    else:
        score = engaged_strength / total

    # 4) Label from score
    if score < 0.4:
        label = "disengaged"
    elif score < 0.7:
        label = "neutral"
    else:
        label = "engaged"

    return score, label


tests = [
    # (idle_ratio, scroll_speed, interaction_count, what you expect)
    (0.70,  10, 0,  "should look disengaged"),
    (0.10, 120, 1,  "should look engaged/neutral"),
    (0.20,  80, 0,  "should look neutral-ish"),
    (0.05, 400, 0,  "might be skimming (neutral)"),
    (0.30, 120, 4,  "should look engaged"),
    (0.50, 120, 2,  "mixed: idle hurts engagement"),
]

for idle_ratio, scroll_speed, interactions, note in tests:
    score, label = fuzzy_engagement(idle_ratio, scroll_speed, interactions)
    print(f"idle={idle_ratio:.2f} speed={scroll_speed:>3} interactions={interactions} -> score={score:.2f} label={label} ({note})")