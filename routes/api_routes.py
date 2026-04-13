import random

from flask import Blueprint, jsonify, request, session, url_for

from db import get_db, now_utc_iso
from logic.state_logic import ensure_user, get_state, save_state, add_achievement
from logic.story_logic import load_stories, get_story, compute_unlocks
from logic.engagement_logic import (
    apply_inactivity_health_decay,
    process_engagement_result,
    get_support_message,
    log_engagement_event,
    mark_book_complete,
    start_reading_session,
    complete_reading_session,
)
from logic.quiz_logic import get_suspicious_reasons, should_trigger_random_end_quiz, grade_quiz
from models.engagement_model import predict_engagement

api_bp = Blueprint("api", __name__, url_prefix="/api")


def get_current_state() -> tuple[str, dict]:
    """Same helper as page routes, but used for API routes."""
    user_id = ensure_user()
    state = get_state(user_id)
    state = apply_inactivity_health_decay(state)
    state = save_state(user_id, state)
    return user_id, state


@api_bp.get("/state")
def api_state():
    user_id, state = get_current_state()

    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    connection = get_db()
    recent_events = connection.execute(
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

    recent_events = [dict(event) for event in recent_events]
    recent_events.reverse()

    return jsonify({
        "state": state,
        "unlocks": unlocks,
        "stories": stories,
        "recent_events": recent_events,
    })


@api_bp.get("/stories")
def api_stories():
    return jsonify(load_stories())


@api_bp.post("/start_reading")
def api_start_reading():
    user_id = ensure_user()
    story_id = str(request.get_json(force=True).get("story_id", "")).strip()

    story = get_story(story_id)
    if story is None:
        return jsonify({"ok": False, "error": "Story not found"}), 404

    session.pop("hmm_state_probabilities", None)

    start_reading_session(user_id, story_id)
    return jsonify({"ok": True})


@api_bp.post("/engagement")
def api_engagement():
    user_id = ensure_user()
    features = request.get_json(force=True)

    story_id = str(features.get("story_id", "")).strip() or "unknown"

    features.setdefault("fast_scroll_bursts", 0)
    features.setdefault("active_reading_ratio", 0.5)
    features.setdefault("max_scroll_speed_px_s", 0.0)

    previous_state_data = session.get("hmm_state_probabilities")

    result = predict_engagement(features, previous_state_data=previous_state_data)
    score = float(result["score"])
    label = result["label"]

    if "state_probabilities" in result:
        session["hmm_state_probabilities"] = result["state_probabilities"]

    state = get_state(user_id)
    state = process_engagement_result(state, score, label, features["idle_ratio"])

    support_message = get_support_message(label)
    state["last_engagement_label"] = label
    state["last_engagement_score"] = score
    state["last_support_message"] = support_message

    save_state(user_id, state)
    log_engagement_event(user_id, story_id, features, score, label)

    return jsonify({
        "score": score,
        "label": label,
        "support_message": support_message,
    })


@api_bp.post("/complete_book")
def api_complete_book():
    user_id = ensure_user()
    payload = request.get_json(force=True)

    story_id = str(payload.get("story_id", "")).strip()
    reading_time = float(payload.get("reading_time", 0))
    scroll_depth = float(payload.get("scroll_depth", 0))
    disengaged_windows = int(payload.get("disengaged_windows", 0))
    focus_loss_ratio = float(payload.get("focus_loss_ratio", 0))
    idle_ratio = float(payload.get("idle_ratio", 0))

    stories = load_stories()
    story_ids = [story["id"] for story in stories]

    if story_id not in story_ids:
        return jsonify({"ok": False, "error": "Invalid story_id"}), 400

    state = get_state(user_id)
    unlocks = compute_unlocks(state, stories)

    if story_id not in unlocks["unlocked_books"]:
        return jsonify({"ok": False, "error": "Story is locked"}), 403

    story = get_story(story_id)
    suspicious_reasons = get_suspicious_reasons(
        story_text=story["text"],
        reading_time=reading_time,
        scroll_depth=scroll_depth,
        disengaged_windows=disengaged_windows,
        focus_loss_ratio=focus_loss_ratio,
        idle_ratio=idle_ratio,
    )

    complete_reading_session(
        user_id=user_id,
        story_id=story_id,
        reading_time=reading_time,
        scroll_depth=scroll_depth,
        suspicious_reasons=suspicious_reasons,
    )

    if "Completed unusually fast" in suspicious_reasons:
        state["last_support_message"] = "That was very quick — let’s do a quick check first 📖"
        save_state(user_id, state)

    should_show_quiz = False
    quiz_reason = ""

    if suspicious_reasons:
        should_show_quiz = True
        quiz_reason = "suspicious"
    elif should_trigger_random_end_quiz(random.random()):
        should_show_quiz = True
        quiz_reason = "random_end_check"

    if should_show_quiz:
        session["pending_completion"] = {
            "story_id": story_id,
            "reason": quiz_reason,
        }
        return jsonify({
            "ok": True,
            "needs_quiz": True,
            "quiz_url": url_for("pages.quiz_page", story_id=story_id),
            "reason": quiz_reason,
            "suspicious_reasons": suspicious_reasons,
        })

    state = mark_book_complete(state, story_id)
    state["last_support_message"] = "Book completed! Great job 📚"
    state = save_state(user_id, state)

    session.pop("hmm_state_probabilities", None)

    unlocks = compute_unlocks(state, stories)

    return jsonify({
        "ok": True,
        "needs_quiz": False,
        "state": state,
        "unlocks": unlocks,
    })


@api_bp.get("/quiz/<story_id>")
def api_get_quiz(story_id: str):
    story = get_story(story_id)
    if story is None:
        return jsonify({"ok": False, "error": "Story not found"}), 404

    return jsonify({
        "ok": True,
        "quiz": story.get("quiz", []),
        "title": story["title"],
    })


@api_bp.post("/quiz/<story_id>")
def api_submit_quiz(story_id: str):
    user_id = ensure_user()
    answers = request.get_json(force=True).get("answers", [])

    story = get_story(story_id)
    if story is None:
        return jsonify({"ok": False, "error": "Story not found"}), 404

    quiz = story.get("quiz", [])
    if not quiz:
        return jsonify({"ok": False, "error": "No quiz for this story"}), 400

    score, total, passed = grade_quiz(quiz, answers)

    connection = get_db()
    connection.execute(
        """
        INSERT INTO quiz_results (user_id, story_id, score, total, passed, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, story_id, score, total, 1 if passed else 0, now_utc_iso()),
    )
    connection.commit()
    connection.close()

    pending_completion = session.get("pending_completion")
    completion_applied = False

    if pending_completion and pending_completion.get("story_id") == story_id:
        state = get_state(user_id)

        if passed:
            state = mark_book_complete(state, story_id)
            state["last_support_message"] = "Nice work — quiz passed! ✅"
            state = save_state(user_id, state)
            completion_applied = True
        else:
            state["last_engagement_label"] = "disengaged"
            state["last_support_message"] = "Quiz not passed — try reading more carefully and have another go 📖"
            state = save_state(user_id, state)

        session.pop("pending_completion", None)

    session.pop("hmm_state_probabilities", None)

    return jsonify({
        "ok": True,
        "score": score,
        "total": total,
        "passed": passed,
        "completion_applied": completion_applied,
    })


@api_bp.post("/select_avatar")
def api_select_avatar():
    user_id = ensure_user()
    avatar = str(request.get_json(force=True).get("avatar", "")).strip()

    state = get_state(user_id)
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    if avatar not in unlocks["unlocked_avatars"]:
        return jsonify({"ok": False, "error": "Avatar locked"}), 403

    state["selected_avatar"] = avatar
    add_achievement(state, "Changed Avatar 🎭")
    state = save_state(user_id, state)

    return jsonify({"ok": True, "state": state})


@api_bp.post("/select_bg")
def api_select_bg():
    user_id = ensure_user()
    background = str(request.get_json(force=True).get("bg", "")).strip()

    state = get_state(user_id)
    stories = load_stories()
    unlocks = compute_unlocks(state, stories)

    if background not in unlocks["unlocked_bgs"]:
        return jsonify({"ok": False, "error": "Background locked"}), 403

    state["selected_bg"] = background
    add_achievement(state, "Changed Background 🖼️")
    state = save_state(user_id, state)

    return jsonify({"ok": True, "state": state})