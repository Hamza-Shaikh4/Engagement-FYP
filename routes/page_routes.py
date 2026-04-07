from flask import Blueprint, render_template, redirect, url_for

from logic.state_logic import ensure_user, get_state, save_state
from logic.story_logic import load_stories, get_story, compute_unlocks
from logic.engagement_logic import apply_inactivity_health_decay
from db import get_db

pages_bp = Blueprint("pages", __name__)


def get_current_state() -> tuple[str, dict]:
    """
    Helper used by many page routes.
    It loads the current user and applies inactivity decay.
    """
    user_id = ensure_user()
    state = get_state(user_id)
    state = apply_inactivity_health_decay(state)
    state = save_state(user_id, state)
    return user_id, state


@pages_bp.get("/")
def home():
    user_id, state = get_current_state()

    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    continue_story = "book1"
    for story_id in unlocks["unlocked_books"]:
        if story_id not in state["completed_books"]:
            continue_story = story_id
            break
    else:
        if unlocks["unlocked_books"]:
            continue_story = unlocks["unlocked_books"][-1]

    return render_template(
        "index.html",
        state=state,
        unlocks=unlocks,
        continue_story=continue_story,
    )


@pages_bp.get("/books")
def books():
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)
    return render_template("books.html", state=state, stories=stories, unlocks=unlocks)


@pages_bp.get("/reading/<story_id>")
def reading(story_id: str):
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    if story_id not in unlocks["unlocked_books"]:
        return redirect(url_for("pages.books"))

    return render_template("reading.html", story_id=story_id, state=state)


@pages_bp.get("/results")
def results():
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)
    return render_template("results.html", state=state, stories=stories, unlocks=unlocks)


@pages_bp.get("/stats")
def stats():
    user_id, state = get_current_state()

    connection = get_db()
    events = connection.execute(
        """
        SELECT score, label, ts
        FROM engagement_events
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (user_id,),
    ).fetchall()
    connection.close()

    from datetime import datetime

    events = [dict(e) for e in events]
    events.reverse()

    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc).astimezone()

    for event in events:
        dt = datetime.fromisoformat(event["ts"])

        # Make sure timestamp is timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone()

        if dt.date() == now.date():
            # Same day
            event["display_time"] = dt.strftime("%H:%M:%S")

        elif dt.date() == (now.date() - timedelta(days=1)):
            # Yesterday
            event["display_time"] = f"Yesterday {dt.strftime('%H:%M')}"

        else:
            # Older date
            event["display_time"] = dt.strftime("%d %b %H:%M")

    return render_template("stats.html", state=state, events=events)


@pages_bp.get("/avatar")
def avatar():
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)
    return render_template("avatar.html", state=state, unlocks=unlocks)


@pages_bp.get("/quiz/<story_id>")
def quiz_page(story_id: str):
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    if story_id not in unlocks["unlocked_books"]:
        return redirect(url_for("pages.books"))

    story = get_story(story_id)
    if story is None:
        return redirect(url_for("pages.books"))

    return render_template(
        "quiz.html",
        story_id=story_id,
        story_title=story["title"],
        state=state,
    )