from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request

from logic.state_logic import (
    ensure_user,
    get_state,
    save_state,
    update_streak_and_last_active_date,
)
from logic.story_logic import load_stories, get_story, compute_unlocks
from logic.engagement_logic import apply_inactivity_health_decay
from db import get_db

pages_bp = Blueprint("pages", __name__)


def maybe_update_daily_streak(state: dict) -> dict:
    """
    Update the user's daily streak when they visit on a new day.
    """
    today = date.today().isoformat()
    previous_last_active = state["last_active_date"]

    if previous_last_active == today:
        return state

    update_streak_and_last_active_date(state)
    return state


def xp_into_current_level(xp: int) -> tuple[int, int]:
    """
    Return:
    - XP gained inside the current level
    - XP needed to complete the current level
    """
    current_level_floor = (max(1, int(xp // 100) + 1) - 1) * 100
    current_level_xp = xp - current_level_floor
    return current_level_xp, 100


def build_books_dialogue(stage_cards: list[dict], state: dict, celebrate: bool) -> list[str]:
    """
    Build a short click-through dialogue for the books page.
    Reward unlocks and quest completions override the normal message.
    """
    current_stage = next((stage for stage in stage_cards if stage["status"] == "current"), None)
    all_complete = bool(stage_cards) and all(stage["status"] == "completed" for stage in stage_cards)

    unlocked_rewards = []
    completed_books = len(state["completed_books"])

    if completed_books >= 1:
        unlocked_rewards.append("Reward unlocked: new avatars are available.")
    if completed_books >= 3:
        unlocked_rewards.append("Reward unlocked: a new background is available.")

    if state["streak"] == 3:
        unlocked_rewards.append("Quest complete: 3-day streak. You earned bonus XP.")
    if state["streak"] == 5:
        unlocked_rewards.append("Quest complete: 5-day streak. You earned bonus XP.")
    if state["health"] >= 90 and completed_books >= 1:
        unlocked_rewards.append("Quest complete: keep your buddy healthy. You earned bonus XP.")

    if celebrate and unlocked_rewards:
        lines = [
            "Nice work. You finished that book.",
            "You earned XP for completing it.",
        ]
        lines.extend(unlocked_rewards)
        lines.append("Open the Avatar Closet to see your rewards.")
        return lines

    if celebrate:
        lines = [
            "Nice work. You finished that book.",
            "You earned XP for completing it.",
        ]

        if current_stage:
            lines.append(f"We’re now in {current_stage['stage_name']}.")
            lines.append(
                f"You’ve completed {current_stage['completed_in_stage']} of "
                f"{current_stage['total_in_stage']} books in this stage."
            )
        elif all_complete:
            lines.append("You’ve cleared every stage.")
        else:
            lines.append("More books are ready when you are.")

        if state["streak"] > 0:
            lines.append(f"Your streak is now {state['streak']} day{'s' if state['streak'] != 1 else ''}.")

        lines.append("Choose your next book when you’re ready.")
        return lines

    if all_complete:
        lines = [
            "We’ve finished the whole adventure.",
            "You can replay any unlocked book from here.",
        ]
        if state["streak"] > 0:
            lines.append(f"Your streak is at {state['streak']} day{'s' if state['streak'] != 1 else ''}.")
        return lines

    if current_stage:
        remaining = current_stage["total_in_stage"] - current_stage["completed_in_stage"]

        lines = [
            f"We’re in {current_stage['stage_name']}.",
            f"You’ve finished {current_stage['completed_in_stage']} of {current_stage['total_in_stage']} books here.",
        ]

        if remaining == 1:
            lines.append("There is one book left in this stage.")
        elif remaining > 1:
            lines.append(f"There are {remaining} books left in this stage.")

        if state["streak"] > 0:
            lines.append(f"Let’s keep the {state['streak']}-day streak going.")

        lines.append("Pick the next book when you’re ready.")
        return lines

    return [
        "This is your books page.",
        "Pick a book to continue.",
    ]


def build_quest_cards(state: dict) -> list[dict]:
    """
    Build quest cards for the quests/progress page.
    """
    completed_books = set(state["completed_books"])
    streak = int(state["streak"])
    health = int(state["health"])
    xp = int(state["xp"])

    quests = [
        {
            "title": "Finish your first book",
            "description": "Complete Book 1 to unlock more content.",
            "progress_text": f"{1 if 'book1' in completed_books else 0}/1",
            "reward": "+40 XP • Outfit unlock",
            "done": "book1" in completed_books,
        },
        {
            "title": "Clear Stage 1",
            "description": "Finish Book 1, Book 2, and Book 3.",
            "progress_text": f"{sum(1 for b in ['book1', 'book2', 'book3'] if b in completed_books)}/3",
            "reward": "+60 XP • Background unlock",
            "done": all(b in completed_books for b in ["book1", "book2", "book3"]),
        },
        {
            "title": "Keep a 3-day streak",
            "description": "Read on three consecutive days.",
            "progress_text": f"{min(streak, 3)}/3",
            "reward": "+30 XP",
            "done": streak >= 3,
        },
        {
            "title": "Keep a 5-day streak",
            "description": "Extend your reading streak to five days.",
            "progress_text": f"{min(streak, 5)}/5",
            "reward": "+50 XP",
            "done": streak >= 5,
        },
        {
            "title": "Protect buddy health",
            "description": "Keep buddy health at 90% or above.",
            "progress_text": f"{min(health, 100)}%",
            "reward": "+25 XP",
            "done": health >= 90,
        },
        {
            "title": "Reach Level 2",
            "description": "Gain enough XP to level up.",
            "progress_text": f"{min(xp, 100)}/100 XP",
            "reward": "Level up reward",
            "done": xp >= 100,
        },
    ]

    return quests


def get_current_state() -> tuple[str, dict]:
    """
    Helper used by many page routes.
    """
    user_id = ensure_user()
    state = get_state(user_id)

    state = apply_inactivity_health_decay(state)
    state = maybe_update_daily_streak(state)

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

    grouped = {}
    for story in stories:
        stage_number = int(story.get("stage", 1))
        grouped.setdefault(stage_number, []).append(story)

    stage_meta = {
        1: {"name": "Forest Trail", "icon": "🌳", "difficulty": "Easy"},
        2: {"name": "Crystal Cave", "icon": "💎", "difficulty": "Medium"},
        3: {"name": "Sky Castle", "icon": "🏰", "difficulty": "Hard"},
        4: {"name": "Shadow Peaks", "icon": "⛰️", "difficulty": "Very Hard"},
    }

    stage_cards = []

    for stage_number in sorted(grouped.keys()):
        stage_stories = grouped[stage_number]
        stage_story_ids = [story["id"] for story in stage_stories]
        completed_in_stage = sum(1 for story_id in stage_story_ids if story_id in state["completed_books"])
        total_in_stage = len(stage_story_ids)

        is_unlocked = stage_number in unlocks.get("unlocked_stages", [1])
        is_completed = completed_in_stage == total_in_stage and total_in_stage > 0

        if is_completed:
            status = "completed"
        elif is_unlocked:
            status = "current"
        else:
            status = "locked"

        books_in_stage = []
        for story in stage_stories:
            story_completed = story["id"] in state["completed_books"]
            story_unlocked = story["id"] in unlocks["unlocked_books"]

            books_in_stage.append({
                "id": story["id"],
                "title": story["title"],
                "summary": story.get("summary", ""),
                "completed": story_completed,
                "unlocked": story_unlocked,
                "href": url_for("pages.reading", story_id=story["id"]) if story_unlocked else None,
            })

        meta = stage_meta.get(
            stage_number,
            {"name": f"Stage {stage_number}", "icon": "📖", "difficulty": "Unknown"},
        )

        stage_cards.append({
            "stage_number": stage_number,
            "stage_name": meta["name"],
            "icon": meta["icon"],
            "difficulty": meta["difficulty"],
            "status": status,
            "completed_in_stage": completed_in_stage,
            "total_in_stage": total_in_stage,
            "books": books_in_stage,
        })

    celebrate = request.args.get("celebrate") == "1"
    dialogue_lines = build_books_dialogue(stage_cards, state, celebrate)

    return render_template(
        "books.html",
        state=state,
        stage_cards=stage_cards,
        dialogue_lines=dialogue_lines,
        celebrate=celebrate,
    )


@pages_bp.get("/reading/<story_id>")
def reading(story_id: str):
    user_id, state = get_current_state()
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    if story_id not in unlocks["unlocked_books"]:
        return redirect(url_for("pages.books"))

    return render_template(
        "reading.html",
        story_id=story_id,
        state=state,
    )


@pages_bp.get("/results")
def results():
    user_id, state = get_current_state()

    quests = build_quest_cards(state)
    completed_quests = sum(1 for q in quests if q["done"])
    current_level_xp, level_goal = xp_into_current_level(state["xp"])

    return render_template(
        "results.html",
        state=state,
        quests=quests,
        completed_quests=completed_quests,
        current_level_xp=current_level_xp,
        level_goal=level_goal,
    )


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

    quiz_results = connection.execute(
        """
        SELECT story_id, score, total, passed, created_at
        FROM quiz_results
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (user_id,),
    ).fetchall()

    connection.close()

    events = [dict(e) for e in events]
    events.reverse()
    quiz_results = [dict(q) for q in quiz_results]

    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc).astimezone()

    for event in events:
        dt = datetime.fromisoformat(event["ts"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone()

        if dt.date() == now.date():
            event["display_time"] = dt.strftime("%H:%M:%S")
        elif dt.date() == (now.date() - timedelta(days=1)):
            event["display_time"] = f"Yesterday {dt.strftime('%H:%M')}"
        else:
            event["display_time"] = dt.strftime("%d %b %H:%M")

    for quiz in quiz_results:
        dt = datetime.fromisoformat(quiz["created_at"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone()

        if dt.date() == now.date():
            quiz["display_time"] = dt.strftime("%H:%M:%S")
        elif dt.date() == (now.date() - timedelta(days=1)):
            quiz["display_time"] = f"Yesterday {dt.strftime('%H:%M')}"
        else:
            quiz["display_time"] = dt.strftime("%d %b %H:%M")

    return render_template(
        "stats.html",
        state=state,
        events=events,
        quiz_results=quiz_results,
    )


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