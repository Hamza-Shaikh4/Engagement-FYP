import json
import uuid
from datetime import date

from flask import session

from config import HEALTH_MAX
from db import get_db, now_utc_iso


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def ensure_user() -> str:
    """Make sure the current visitor has a user id in session."""
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]


def default_state(user_id: str) -> dict:
    """Return default state for a new user."""
    return {
        "user_id": user_id,
        "xp": 0,
        "level": 1,
        "health": 60,
        "streak": 0,
        "last_active_date": None,
        "selected_avatar": "default",
        "selected_bg": "bg-default",
        "completed_books_json": "[]",
        "achievements_json": "[]",
        "last_engagement_label": "neutral",
        "last_engagement_score": 0.5,
        "last_support_message": "Ready to read?",
        "health_last_decay_date": None,
        "disengaged_streak_windows": 0,
        "engaged_streak_windows": 0,
        "idle_streak_windows": 0,
        "idle_penalty_latched": 0,
    }


def create_user_if_needed(user_id: str) -> None:
    """Create a user and default state if they do not exist yet."""
    connection = get_db()

    # Make sure the tables exist in case the DB file was deleted
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            user_id TEXT PRIMARY KEY,
            xp INTEGER NOT NULL,
            level INTEGER NOT NULL,
            health INTEGER NOT NULL,
            streak INTEGER NOT NULL,
            last_active_date TEXT,
            selected_avatar TEXT NOT NULL,
            selected_bg TEXT NOT NULL,
            completed_books_json TEXT NOT NULL,
            achievements_json TEXT NOT NULL,
            last_engagement_label TEXT NOT NULL,
            last_engagement_score REAL NOT NULL,
            last_support_message TEXT NOT NULL,
            health_last_decay_date TEXT,
            disengaged_streak_windows INTEGER NOT NULL DEFAULT 0,
            engaged_streak_windows INTEGER NOT NULL DEFAULT 0,
            idle_streak_windows INTEGER NOT NULL DEFAULT 0,
            idle_penalty_latched INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        """
    )

    existing = connection.execute(
        "SELECT user_id FROM state WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if existing is None:
        connection.execute(
            "INSERT OR IGNORE INTO users(user_id, created_at) VALUES (?, ?)",
            (user_id, now_utc_iso()),
        )

        state = default_state(user_id)
        connection.execute(
            """
            INSERT INTO state (
                user_id, xp, level, health, streak, last_active_date,
                selected_avatar, selected_bg, completed_books_json, achievements_json,
                last_engagement_label, last_engagement_score, last_support_message,
                health_last_decay_date, disengaged_streak_windows, engaged_streak_windows,
                idle_streak_windows, idle_penalty_latched
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state["user_id"],
                state["xp"],
                state["level"],
                state["health"],
                state["streak"],
                state["last_active_date"],
                state["selected_avatar"],
                state["selected_bg"],
                state["completed_books_json"],
                state["achievements_json"],
                state["last_engagement_label"],
                state["last_engagement_score"],
                state["last_support_message"],
                state["health_last_decay_date"],
                state["disengaged_streak_windows"],
                state["engaged_streak_windows"],
                state["idle_streak_windows"],
                state["idle_penalty_latched"],
            ),
        )
        connection.commit()

    connection.close()


def get_state(user_id: str) -> dict:
    """Load and decode one user's state."""
    create_user_if_needed(user_id)

    connection = get_db()
    row = connection.execute(
        "SELECT * FROM state WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    connection.close()

    state = dict(row)
    state["completed_books"] = json.loads(state["completed_books_json"])
    state["achievements"] = json.loads(state["achievements_json"])
    return state


def save_state(user_id: str, state: dict) -> dict:
    """Save one user's state back to the database."""
    connection = get_db()
    connection.execute(
        """
        UPDATE state SET
            xp = ?,
            level = ?,
            health = ?,
            streak = ?,
            last_active_date = ?,
            selected_avatar = ?,
            selected_bg = ?,
            completed_books_json = ?,
            achievements_json = ?,
            last_engagement_label = ?,
            last_engagement_score = ?,
            last_support_message = ?,
            health_last_decay_date = ?,
            disengaged_streak_windows = ?,
            engaged_streak_windows = ?,
            idle_streak_windows = ?,
            idle_penalty_latched = ?
        WHERE user_id = ?
        """,
        (
            state["xp"],
            state["level"],
            state["health"],
            state["streak"],
            state["last_active_date"],
            state["selected_avatar"],
            state["selected_bg"],
            json.dumps(state["completed_books"]),
            json.dumps(state["achievements"]),
            state["last_engagement_label"],
            state["last_engagement_score"],
            state["last_support_message"],
            state["health_last_decay_date"],
            state["disengaged_streak_windows"],
            state["engaged_streak_windows"],
            state["idle_streak_windows"],
            state["idle_penalty_latched"],
            user_id,
        ),
    )
    connection.commit()
    connection.close()
    return get_state(user_id)


def add_achievement(state: dict, achievement_name: str) -> None:
    """Add an achievement if it is not already in the list."""
    if achievement_name not in state["achievements"]:
        state["achievements"].append(achievement_name)


def calculate_level_from_xp(xp: int) -> int:
    """Simple level rule: every 100 XP gives a new level."""
    return 1 + (xp // 100)


def update_streak_and_last_active_date(state: dict) -> None:
    """
    Update reading streak based on the user's last active date.
    """
    today = date.today()
    last_date = state["last_active_date"]

    if last_date is None:
        state["streak"] = 1
    else:
        previous_day = date.fromisoformat(last_date)
        days_between = (today - previous_day).days

        if days_between == 0:
            pass
        elif days_between == 1:
            state["streak"] += 1
        else:
            state["streak"] = 1

    state["last_active_date"] = today.isoformat()

    if state["streak"] == 3:
        add_achievement(state, "3-Day Streak 🔥")
    if state["streak"] == 5:
        add_achievement(state, "5-Day Streak 🔥🔥")


def reset_health_to_full(state: dict) -> None:
    """Reset health to the maximum value."""
    state["health"] = HEALTH_MAX