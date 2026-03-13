from datetime import date

from config import (
    HEALTH_MIN,
    HEALTH_MAX,
    ENGAGED_WINDOWS_FOR_PLUS1,
    ENGAGED_HEALTH_BONUS,
    DISENGAGED_WINDOWS_TRIGGER,
    DISENGAGED_HEALTH_PENALTY,
    IDLE_HIGH_THRESHOLD,
    IDLE_RECOVER_THRESHOLD,
    IDLE_WINDOWS_TRIGGER,
    IDLE_HEALTH_PENALTY,
    INACTIVITY_DAYS_TRIGGER,
    INACTIVITY_HEALTH_PENALTY,
)
from db import get_db, now_utc_iso
from logic.state_logic import (
    clamp,
    add_achievement,
    calculate_level_from_xp,
    update_streak_and_last_active_date,
    reset_health_to_full,
)


def apply_inactivity_health_decay(state: dict) -> dict:
    """
    If the user has been away for 2 or more days, reduce health once per day.
    """
    today = date.today().isoformat()

    if state["health_last_decay_date"] == today:
        return state

    last_active_date = state["last_active_date"]
    if last_active_date is None:
        state["health_last_decay_date"] = today
        return state

    inactive_days = (date.today() - date.fromisoformat(last_active_date)).days

    if inactive_days >= INACTIVITY_DAYS_TRIGGER:
        state["health"] = clamp(
            state["health"] - INACTIVITY_HEALTH_PENALTY,
            HEALTH_MIN,
            HEALTH_MAX,
        )

    state["health_last_decay_date"] = today
    return state


def mark_book_complete(state: dict, story_id: str) -> dict:
    """
    Apply all rewards for completing a book.
    """
    if story_id not in state["completed_books"]:
        state["completed_books"].append(story_id)
        add_achievement(state, f"Finished {story_id.upper()}")

        old_level = state["level"]
        state["xp"] += 40
        state["level"] = calculate_level_from_xp(state["xp"])

        reset_health_to_full(state)

        if state["level"] > old_level:
            add_achievement(state, f"Level Up! Reached Level {state['level']}")

    update_streak_and_last_active_date(state)
    return state


def process_engagement_result(state: dict, score: float, label: str, idle_ratio: float) -> dict:
    """
    Apply health and streak rules after one engagement window.
    """
    # Engaged for 30 seconds -> +1 health
    if label == "engaged":
        state["engaged_streak_windows"] += 1
        if state["engaged_streak_windows"] >= ENGAGED_WINDOWS_FOR_PLUS1:
            state["health"] = clamp(
                state["health"] + ENGAGED_HEALTH_BONUS,
                HEALTH_MIN,
                HEALTH_MAX,
            )
            state["engaged_streak_windows"] = 0
    else:
        state["engaged_streak_windows"] = 0

    # Disengaged for 30 seconds -> -2 health
    if label == "disengaged":
        state["disengaged_streak_windows"] += 1
        if state["disengaged_streak_windows"] >= DISENGAGED_WINDOWS_TRIGGER:
            state["health"] = clamp(
                state["health"] - DISENGAGED_HEALTH_PENALTY,
                HEALTH_MIN,
                HEALTH_MAX,
            )
            state["disengaged_streak_windows"] = 0
    else:
        state["disengaged_streak_windows"] = 0

    # Idle cap: only penalise once until user becomes active again
    if idle_ratio >= IDLE_HIGH_THRESHOLD:
        state["idle_streak_windows"] += 1
    else:
        state["idle_streak_windows"] = 0

    if (
        state["idle_penalty_latched"] == 0
        and state["idle_streak_windows"] >= IDLE_WINDOWS_TRIGGER
    ):
        state["health"] = clamp(
            state["health"] - IDLE_HEALTH_PENALTY,
            HEALTH_MIN,
            HEALTH_MAX,
        )
        state["idle_penalty_latched"] = 1

    if idle_ratio < IDLE_RECOVER_THRESHOLD:
        state["idle_penalty_latched"] = 0
        state["idle_streak_windows"] = 0

    return state


def get_support_message(label: str) -> str:
    """Return a simple supportive message for the current engagement label."""
    if label == "disengaged":
        return "Tiny goal: read one more paragraph 💛"
    if label == "neutral":
        return "Nice! Keep going — you’re close to an unlock ⭐"
    return "You’re locked in! 🚀"


def log_engagement_event(user_id: str, story_id: str, features: dict, score: float, label: str) -> None:
    """Save one engagement prediction to the database."""
    connection = get_db()
    connection.execute(
        """
        INSERT INTO engagement_events
        (user_id, ts, story_id, idle_ratio, scroll_speed_px_s, scroll_depth_ratio,
         focus_loss_ratio, nav_rate_per_min, interaction_rate_per_min, score, label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            now_utc_iso(),
            story_id,
            features["idle_ratio"],
            features["scroll_speed_px_s"],
            features["scroll_depth_ratio"],
            features["focus_loss_ratio"],
            features["nav_rate_per_min"],
            features["interaction_rate_per_min"],
            score,
            label,
        ),
    )
    connection.commit()
    connection.close()


def start_reading_session(user_id: str, story_id: str) -> None:
    """Record the start of a reading session."""
    connection = get_db()
    connection.execute(
        """
        INSERT INTO reading_sessions (user_id, story_id, started_at)
        VALUES (?, ?, ?)
        """,
        (user_id, story_id, now_utc_iso()),
    )
    connection.commit()
    connection.close()


def complete_reading_session(
    user_id: str,
    story_id: str,
    reading_time: float,
    scroll_depth: float,
    suspicious_reasons: list[str],
) -> None:
    """Update the latest reading session for this story."""
    connection = get_db()

    latest_session = connection.execute(
        """
        SELECT id
        FROM reading_sessions
        WHERE user_id = ? AND story_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, story_id),
    ).fetchone()

    if latest_session is not None:
        connection.execute(
            """
            UPDATE reading_sessions
            SET completed_at = ?, reading_time_s = ?, scroll_depth = ?, suspicious = ?, suspicious_reason = ?
            WHERE id = ?
            """,
            (
                now_utc_iso(),
                reading_time,
                scroll_depth,
                1 if suspicious_reasons else 0,
                "; ".join(suspicious_reasons),
                latest_session["id"],
            ),
        )
        connection.commit()

    connection.close()