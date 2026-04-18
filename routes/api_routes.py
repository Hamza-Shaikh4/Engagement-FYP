import random
from typing import Optional, Tuple, List

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
from logic.quiz_logic import (
    get_suspicious_reasons,
    should_trigger_random_end_quiz,
    grade_quiz,
)
from models.engagement_model import predict_engagement

api_bp = Blueprint("api", __name__, url_prefix="/api")

CALIBRATION_BOOK_ID = "book1"
CALIBRATION_MIN_WINDOWS = 2
CALIBRATION_MAX_FOCUS_LOSS = 0.20
CALIBRATION_MAX_IDLE_RATIO = 0.45


def get_current_state() -> Tuple[str, dict]:
    """Same helper as page routes, but used for API routes."""
    user_id = ensure_user()
    state = get_state(user_id)
    state = apply_inactivity_health_decay(state)
    state = save_state(user_id, state)
    return user_id, state


def get_user_calibration(user_id: str) -> Optional[dict]:
    connection = get_db()
    row = connection.execute(
        """
        SELECT *
        FROM user_calibration
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def estimate_word_count(text: str) -> int:
    return max(1, len(text.split()))


def base_expected_reading_seconds(story: dict) -> float:
    """
    Rough child-reading baseline.
    95 words per minute is deliberately conservative.
    """
    word_count = estimate_word_count(story.get("text", ""))
    words_per_second = 95 / 60
    return max(30.0, word_count / words_per_second)


def calibrated_pace_factor(calibration: Optional[dict], stories: list[dict]) -> float:
    """
    Use Book 1 calibration to slightly scale expected reading time.
    Clamped so calibration only nudges the model, not dominate it.
    """
    if not calibration:
        return 1.0

    if int(calibration.get("is_valid", 0)) != 1:
        return 1.0

    calibration_story_id = str(calibration.get("calibration_book_id", "")).strip()
    calibration_story = next((s for s in stories if s["id"] == calibration_story_id), None)
    if calibration_story is None:
        return 1.0

    expected_for_calibration = base_expected_reading_seconds(calibration_story)
    actual_calibration_time = float(calibration.get("avg_reading_time_s", 0.0))

    if actual_calibration_time <= 0:
        return 1.0

    factor = actual_calibration_time / expected_for_calibration
    return max(0.75, min(1.60, factor))


def expected_reading_seconds_for_story(story: dict, calibration: Optional[dict], stories: list[dict]) -> float:
    base_seconds = base_expected_reading_seconds(story)
    factor = calibrated_pace_factor(calibration, stories)
    return base_seconds * factor


def start_calibration_aggregate_if_needed(user_id: str, story_id: str) -> None:
    """
    Start lightweight aggregation for Book 1 only if no calibration exists yet.
    """
    if story_id != CALIBRATION_BOOK_ID:
        return

    existing = get_user_calibration(user_id)
    if existing is not None:
        return

    session["calibration_aggregate"] = {
        "story_id": story_id,
        "windows": 0,
        "sum_scroll_speed": 0.0,
        "sum_idle_ratio": 0.0,
        "sum_scroll_depth": 0.0,
        "sum_interaction_rate": 0.0,
        "sum_active_reading_ratio": 0.0,
        "max_focus_loss_ratio": 0.0,
        "max_idle_ratio": 0.0,
    }


def update_calibration_aggregate(features: dict) -> None:
    """
    Update Book 1 calibration aggregate.

    focus_loss_ratio is tracked only for validity checks,
    not as part of the baseline itself.
    """
    aggregate = session.get("calibration_aggregate")
    if not aggregate:
        return

    story_id = str(features.get("story_id", "")).strip()
    if aggregate.get("story_id") != story_id:
        return

    idle_ratio = float(features.get("idle_ratio", 0.0))
    scroll_speed = float(features.get("scroll_speed_px_s", 0.0))
    scroll_depth = float(features.get("scroll_depth_ratio", 0.0))
    focus_loss = float(features.get("focus_loss_ratio", 0.0))
    interaction_rate = float(features.get("interaction_rate_per_min", 0.0))
    active_reading_ratio = float(features.get("active_reading_ratio", 0.0))

    aggregate["windows"] += 1
    aggregate["sum_scroll_speed"] += scroll_speed
    aggregate["sum_idle_ratio"] += idle_ratio
    aggregate["sum_scroll_depth"] += scroll_depth
    aggregate["sum_interaction_rate"] += interaction_rate
    aggregate["sum_active_reading_ratio"] += active_reading_ratio
    aggregate["max_focus_loss_ratio"] = max(aggregate["max_focus_loss_ratio"], focus_loss)
    aggregate["max_idle_ratio"] = max(aggregate["max_idle_ratio"], idle_ratio)

    session["calibration_aggregate"] = aggregate


def save_calibration_result(
    user_id: str,
    story_id: str,
    reading_time: float,
    self_report: str,
    quiz_score: int,
    quiz_total: int,
    passed: bool,
    suspicious_reasons: List[str],
) -> Optional[dict]:
    """
    Save calibration baseline if the Book 1 session was valid enough.
    """
    aggregate = session.get("calibration_aggregate")
    if not aggregate:
        return None

    windows = int(aggregate.get("windows", 0))
    is_valid = 1

    if windows < CALIBRATION_MIN_WINDOWS:
        is_valid = 0

    if self_report == "no":
        is_valid = 0

    if not passed:
        is_valid = 0

    if "Completed unusually fast" in suspicious_reasons:
        is_valid = 0

    if "Completed much faster than expected" in suspicious_reasons:
        is_valid = 0

    if float(aggregate.get("max_focus_loss_ratio", 0.0)) > CALIBRATION_MAX_FOCUS_LOSS:
        is_valid = 0

    if float(aggregate.get("max_idle_ratio", 0.0)) > CALIBRATION_MAX_IDLE_RATIO:
        is_valid = 0

    avg_scroll_speed = float(aggregate["sum_scroll_speed"]) / max(1, windows)
    avg_idle_ratio = float(aggregate["sum_idle_ratio"]) / max(1, windows)
    avg_scroll_depth = float(aggregate["sum_scroll_depth"]) / max(1, windows)
    avg_interaction_rate = float(aggregate["sum_interaction_rate"]) / max(1, windows)
    avg_active_reading_ratio = float(aggregate["sum_active_reading_ratio"]) / max(1, windows)

    connection = get_db()
    connection.execute(
        """
        INSERT OR REPLACE INTO user_calibration (
            user_id,
            calibration_book_id,
            self_report,
            avg_scroll_speed,
            avg_idle_ratio,
            avg_scroll_depth,
            avg_interaction_rate,
            avg_active_reading_ratio,
            avg_reading_time_s,
            quiz_score,
            quiz_total,
            is_valid,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            story_id,
            self_report,
            avg_scroll_speed,
            avg_idle_ratio,
            avg_scroll_depth,
            avg_interaction_rate,
            avg_active_reading_ratio,
            float(reading_time),
            int(quiz_score),
            int(quiz_total),
            int(is_valid),
            now_utc_iso(),
        ),
    )
    connection.commit()

    row = connection.execute(
        """
        SELECT *
        FROM user_calibration
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    connection.close()

    session.pop("calibration_aggregate", None)
    return dict(row) if row else None


@api_bp.get("/state")
def api_state():
    user_id, state = get_current_state()

    stories = load_stories()
    unlocks = compute_unlocks(state, stories)
    calibration = get_user_calibration(user_id)

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
        "calibration": calibration,
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

    start_calibration_aggregate_if_needed(user_id, story_id)
    start_reading_session(user_id, story_id)
    return jsonify({"ok": True})


@api_bp.post("/engagement")
def api_engagement():
    user_id = ensure_user()
    incoming_features = request.get_json(force=True)

    story_id = str(incoming_features.get("story_id", "")).strip() or "unknown"
    features = dict(incoming_features)

    previous_state_data = session.get("hmm_state_probabilities")
    calibration = get_user_calibration(user_id)

    story = get_story(story_id)
    stories = load_stories()

    if story is not None:
        expected_seconds = expected_reading_seconds_for_story(story, calibration, stories)
        elapsed_reading_time_s = float(features.get("elapsed_reading_time_s", 0.0))
        current_progress_ratio = float(features.get("scroll_depth_ratio", 0.0))

        expected_progress_ratio = min(1.0, elapsed_reading_time_s / max(1.0, expected_seconds))

        raw_ahead_of_expected_ratio = max(0.0, current_progress_ratio - expected_progress_ratio)

        # Depth becomes less reliable as a direct proxy near the end of a book,
        # so soften the pace penalty later in the session.
        end_softening = 1.0
        if current_progress_ratio >= 0.75:
            end_softening = 0.65
        elif current_progress_ratio >= 0.55:
            end_softening = 0.80

        ahead_of_expected_ratio = raw_ahead_of_expected_ratio * end_softening

        features["expected_reading_time_s"] = expected_seconds
        features["expected_progress_ratio"] = expected_progress_ratio
        features["ahead_of_expected_ratio"] = ahead_of_expected_ratio
    else:
        features["expected_reading_time_s"] = 0.0
        features["expected_progress_ratio"] = 0.0
        features["ahead_of_expected_ratio"] = 0.0

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

    update_calibration_aggregate(features)

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

    calibration = get_user_calibration(user_id)
    expected_seconds = expected_reading_seconds_for_story(story, calibration, stories)

    if scroll_depth >= 0.80 and reading_time < (expected_seconds * 0.45):
        suspicious_reasons.append("Completed much faster than expected")

    complete_reading_session(
        user_id=user_id,
        story_id=story_id,
        reading_time=reading_time,
        scroll_depth=scroll_depth,
        suspicious_reasons=suspicious_reasons,
    )

    if (
        "Completed unusually fast" in suspicious_reasons
        or "Completed much faster than expected" in suspicious_reasons
    ):
        state["last_support_message"] = "That was very quick — let’s do a quick check first 📖"
        save_state(user_id, state)

    calibration = get_user_calibration(user_id)
    if story_id == CALIBRATION_BOOK_ID and calibration is None:
        session["pending_completion"] = {
            "story_id": story_id,
            "reading_time": reading_time,
            "suspicious_reasons": suspicious_reasons,
            "calibration_required": True,
        }
        return jsonify({
            "ok": True,
            "calibration_required": True,
            "calibration_prompt": "Did you feel focused while reading this story?",
        })

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
            "reading_time": reading_time,
            "suspicious_reasons": suspicious_reasons,
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
    state = save_state(user_id, state)
    unlocks = compute_unlocks(state, stories)

    return jsonify({
        "ok": True,
        "needs_quiz": False,
        "state": state,
        "unlocks": unlocks,
    })


@api_bp.post("/calibration_response")
def api_calibration_response():
    payload = request.get_json(force=True)

    story_id = str(payload.get("story_id", "")).strip()
    self_report = str(payload.get("self_report", "")).strip().lower()

    if self_report not in {"yes", "somewhat", "no"}:
        return jsonify({"ok": False, "error": "Invalid calibration response"}), 400

    pending_completion = session.get("pending_completion")
    if not pending_completion or pending_completion.get("story_id") != story_id:
        return jsonify({"ok": False, "error": "No pending calibration"}), 400

    pending_completion["calibration_self_report"] = self_report
    session["pending_completion"] = pending_completion

    return jsonify({
        "ok": True,
        "needs_quiz": True,
        "quiz_url": url_for("pages.quiz_page", story_id=story_id),
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
    calibration_saved = False
    calibration_valid = False

    if pending_completion and pending_completion.get("story_id") == story_id:
        if passed:
            state = get_state(user_id)
            state = mark_book_complete(state, story_id)
            save_state(user_id, state)
            completion_applied = True

        if pending_completion.get("calibration_required"):
            saved = save_calibration_result(
                user_id=user_id,
                story_id=story_id,
                reading_time=float(pending_completion.get("reading_time", 0)),
                self_report=pending_completion.get("calibration_self_report", "somewhat"),
                quiz_score=score,
                quiz_total=total,
                passed=passed,
                suspicious_reasons=pending_completion.get("suspicious_reasons", []),
            )
            calibration_saved = saved is not None
            calibration_valid = bool(saved and int(saved.get("is_valid", 0)) == 1)

        session.pop("pending_completion", None)

    return jsonify({
        "ok": True,
        "score": score,
        "total": total,
        "passed": passed,
        "completion_applied": completion_applied,
        "calibration_saved": calibration_saved,
        "calibration_valid": calibration_valid,
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