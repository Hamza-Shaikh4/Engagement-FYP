from __future__ import annotations

import json
import os
import random
import sqlite3
import uuid
from datetime import datetime, date, timezone

from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from fuzzy_logic import fuzzy_engagement


APP_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "dev-secret-change-me"

    app.config["DB_PATH"] = os.path.join(APP_DIR, "app.db")
    app.config["STORIES_PATH"] = os.path.join(APP_DIR, "static", "stories.json")

    # ----------------------------
    # Constants
    # ----------------------------
    HEALTH_MIN = 30
    HEALTH_MAX = 100

    ENGAGED_WINDOWS_FOR_PLUS1 = 3   # 3 x 10s = 30s
    ENGAGED_PLUS = 1

    IDLE_HIGH = 0.92
    IDLE_RECOVER = 0.60
    IDLE_WINDOWS_TRIGGER = 3
    IDLE_PENALTY = 2

    DISENGAGED_WINDOWS_TRIGGER = 3
    DISENGAGED_PENALTY = 2

    INACTIVITY_DAYS_TRIGGER = 2
    INACTIVITY_PENALTY = 5

    RANDOM_END_QUIZ_CHANCE = 0.25

    # ----------------------------
    # DB helpers
    # ----------------------------
    def db() -> sqlite3.Connection:
        con = sqlite3.connect(app.config["DB_PATH"])
        con.row_factory = sqlite3.Row
        return con

    def now_utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def clamp(n: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, n))

    def init_db() -> None:
        con = db()
        cur = con.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
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

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS engagement_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              ts TEXT NOT NULL,
              story_id TEXT NOT NULL,
              idle_ratio REAL,
              scroll_speed_px_s REAL,
              scroll_depth_ratio REAL,
              focus_loss_ratio REAL,
              nav_rate_per_min REAL,
              interaction_rate_per_min REAL,
              score REAL,
              label TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reading_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              story_id TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              reading_time_s REAL DEFAULT 0,
              scroll_depth REAL DEFAULT 0,
              suspicious INTEGER NOT NULL DEFAULT 0,
              suspicious_reason TEXT DEFAULT ''
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT NOT NULL,
              story_id TEXT NOT NULL,
              score INTEGER NOT NULL,
              total INTEGER NOT NULL,
              passed INTEGER NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )

        def add_column_if_missing(table: str, column: str, coltype: str):
            cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

        add_column_if_missing("state", "health_last_decay_date", "TEXT")
        add_column_if_missing("state", "disengaged_streak_windows", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("state", "engaged_streak_windows", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("state", "idle_streak_windows", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("state", "idle_penalty_latched", "INTEGER NOT NULL DEFAULT 0")

        con.commit()
        con.close()

    def load_stories() -> list[dict]:
        with open(app.config["STORIES_PATH"], "r", encoding="utf-8") as f:
            return json.load(f)

    def get_story(story_id: str) -> dict | None:
        for story in load_stories():
            if story["id"] == story_id:
                return story
        return None

    def ensure_user() -> str:
        if "user_id" not in session:
            session["user_id"] = str(uuid.uuid4())
        return session["user_id"]

    def default_state_row(user_id: str) -> dict:
        return dict(
            user_id=user_id,
            xp=0,
            level=1,
            health=60,
            streak=0,
            last_active_date=None,
            selected_avatar="🙂",
            selected_bg="bg-default",
            completed_books_json=json.dumps([]),
            achievements_json=json.dumps([]),
            last_engagement_label="neutral",
            last_engagement_score=0.5,
            last_support_message="Ready to read?",
            health_last_decay_date=None,
            disengaged_streak_windows=0,
            engaged_streak_windows=0,
            idle_streak_windows=0,
            idle_penalty_latched=0,
        )

    def get_state(user_id: str) -> dict:
        con = db()
        row = con.execute("SELECT * FROM state WHERE user_id = ?", (user_id,)).fetchone()
        con.close()

        if row is None:
            con = db()
            con.execute(
                "INSERT OR IGNORE INTO users(user_id, created_at) VALUES (?, ?)",
                (user_id, now_utc_iso()),
            )
            con.execute(
                """
                INSERT OR REPLACE INTO state
                (user_id, xp, level, health, streak, last_active_date, selected_avatar, selected_bg,
                 completed_books_json, achievements_json, last_engagement_label, last_engagement_score, last_support_message,
                 health_last_decay_date, disengaged_streak_windows, engaged_streak_windows, idle_streak_windows, idle_penalty_latched)
                VALUES
                (:user_id, :xp, :level, :health, :streak, :last_active_date, :selected_avatar, :selected_bg,
                 :completed_books_json, :achievements_json, :last_engagement_label, :last_engagement_score, :last_support_message,
                 :health_last_decay_date, :disengaged_streak_windows, :engaged_streak_windows, :idle_streak_windows, :idle_penalty_latched)
                """,
                default_state_row(user_id),
            )
            con.commit()
            con.close()

            con = db()
            row = con.execute("SELECT * FROM state WHERE user_id = ?", (user_id,)).fetchone()
            con.close()

        st = dict(row)
        st["completed_books"] = json.loads(st["completed_books_json"])
        st["achievements"] = json.loads(st["achievements_json"])
        return st

    def save_state(user_id: str, st: dict) -> dict:
        con = db()
        con.execute(
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
                int(st["xp"]),
                int(st["level"]),
                int(st["health"]),
                int(st["streak"]),
                st["last_active_date"],
                st["selected_avatar"],
                st["selected_bg"],
                json.dumps(st["completed_books"]),
                json.dumps(st["achievements"]),
                st["last_engagement_label"],
                float(st["last_engagement_score"]),
                st["last_support_message"],
                st.get("health_last_decay_date"),
                int(st.get("disengaged_streak_windows", 0)),
                int(st.get("engaged_streak_windows", 0)),
                int(st.get("idle_streak_windows", 0)),
                int(st.get("idle_penalty_latched", 0)),
                user_id,
            ),
        )
        con.commit()
        con.close()
        return get_state(user_id)

    def calc_level_from_xp(xp: int) -> int:
        return 1 + (xp // 100)

    def add_achievement(st: dict, name: str) -> None:
        if name not in st["achievements"]:
            st["achievements"].append(name)

    def award_xp_and_reset_health(st: dict, xp_gain: int) -> dict:
        old_level = st["level"]
        st["xp"] += xp_gain
        st["level"] = calc_level_from_xp(st["xp"])

        # completion or level-up resets health
        st["health"] = HEALTH_MAX

        if st["level"] > old_level:
            add_achievement(st, f"Level Up! Reached Level {st['level']}")
        return st

    def apply_inactivity_health_decay(st: dict) -> dict:
        today = date.today()
        today_s = today.isoformat()

        if st.get("health_last_decay_date") == today_s:
            return st

        last = st.get("last_active_date")
        if not last:
            st["health_last_decay_date"] = today_s
            return st

        last_d = date.fromisoformat(last)
        days_inactive = (today - last_d).days

        if days_inactive >= INACTIVITY_DAYS_TRIGGER:
            st["health"] = clamp(st["health"] - INACTIVITY_PENALTY, HEALTH_MIN, HEALTH_MAX)

        st["health_last_decay_date"] = today_s
        return st

    def compute_unlocks(st: dict, stories: list[dict]) -> dict:
        completed = set(st["completed_books"])
        story_ids = [s["id"] for s in stories]

        unlocked_books = []
        for i, sid in enumerate(story_ids):
            if i == 0:
                unlocked_books.append(sid)
            else:
                if story_ids[i - 1] in completed:
                    unlocked_books.append(sid)

        unlocked_avatars = ["🙂"]
        if "book1" in completed:
            unlocked_avatars.append("🧑‍🚀")
        if "book2" in completed:
            unlocked_avatars.append("🧙")
        if "book3" in completed:
            unlocked_avatars.append("🦸")
        if st["streak"] >= 5:
            unlocked_avatars.append("🤖")

        unlocked_bgs = ["bg-default"]
        if "book2" in completed:
            unlocked_bgs.append("bg-space")
        if "book3" in completed:
            unlocked_bgs.append("bg-forest")

        return {
            "unlocked_books": unlocked_books,
            "unlocked_avatars": unlocked_avatars,
            "unlocked_bgs": unlocked_bgs,
        }

    def update_streak_and_activity(st: dict) -> None:
        today = date.today()
        last = st["last_active_date"]

        if last is None:
            st["streak"] = 1
        else:
            last_d = date.fromisoformat(last)
            if last_d == today:
                pass
            else:
                delta = (today - last_d).days
                if delta == 1:
                    st["streak"] += 1
                else:
                    st["streak"] = 1

        st["last_active_date"] = today.isoformat()

        if st["streak"] == 3:
            add_achievement(st, "3-Day Streak 🔥")
        if st["streak"] == 5:
            add_achievement(st, "5-Day Streak 🔥🔥")

    def mark_book_complete(user_id: str, story_id: str) -> dict:
        st = get_state(user_id)

        if story_id not in st["completed_books"]:
            st["completed_books"].append(story_id)
            add_achievement(st, f"Finished {story_id.upper()}")
            st = award_xp_and_reset_health(st, xp_gain=40)

        update_streak_and_activity(st)
        return save_state(user_id, st)

    init_db()

    @app.before_request
    def _ensure_user_every_request():
        ensure_user()

    # ----------------------------
    # Pages
    # ----------------------------
    @app.get("/")
    def home():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)

        continue_story = "book1"
        for sid in unlocks["unlocked_books"]:
            if sid not in st["completed_books"]:
                continue_story = sid
                break
        else:
            if unlocks["unlocked_books"]:
                continue_story = unlocks["unlocked_books"][-1]

        return render_template("index.html", state=st, unlocks=unlocks, continue_story=continue_story)

    @app.get("/books")
    def books():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)
        return render_template("books.html", state=st, stories=stories, unlocks=unlocks)

    @app.get("/reading/<story_id>")
    def reading(story_id: str):
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)

        if story_id not in unlocks["unlocked_books"]:
            return redirect(url_for("books"))

        return render_template("reading.html", story_id=story_id, state=st)

    @app.get("/results")
    def results():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)
        return render_template("results.html", state=st, stories=stories, unlocks=unlocks)

    @app.get("/avatar")
    def avatar():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)
        return render_template("avatar.html", state=st, unlocks=unlocks)


    @app.get("/stats")
    def stats():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        con = db()
        events = con.execute(
            """
            SELECT score, label, ts
            FROM engagement_events
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
        con.close()

        events = [dict(e) for e in events]
        events.reverse()

        return render_template("stats.html", state=st, events=events)

    @app.get("/quiz/<story_id>")
    def quiz_page(story_id: str):
        user_id = ensure_user()
        st = get_state(user_id)
        stories = load_stories()
        unlocks = compute_unlocks(st, stories)

        if story_id not in unlocks["unlocked_books"]:
            return redirect(url_for("books"))

        story = get_story(story_id)
        if not story:
            return redirect(url_for("books"))

        return render_template("quiz.html", story_id=story_id, story_title=story["title"], state=st)

    # ----------------------------
    # APIs
    # ----------------------------
    @app.get("/api/state")
    def api_state():
        user_id = ensure_user()
        st = get_state(user_id)
        st = apply_inactivity_health_decay(st)
        st = save_state(user_id, st)

        stories = load_stories()
        unlocks = compute_unlocks(st, stories)

        con = db()
        recent_events = con.execute(
            """
            SELECT score, label, ts
            FROM engagement_events
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
        con.close()

        recent_events = [dict(r) for r in recent_events]
        recent_events.reverse()

        return jsonify({"state": st, "unlocks": unlocks, "stories": stories, "recent_events": recent_events})

    @app.get("/api/stories")
    def api_stories():
        return jsonify(load_stories())

    @app.post("/api/start_reading")
    def api_start_reading():
        user_id = ensure_user()
        data = request.get_json(force=True)
        story_id = str(data.get("story_id", "")).strip()

        story = get_story(story_id)
        if not story:
            return jsonify({"ok": False, "error": "Story not found"}), 404

        con = db()
        con.execute(
            """
            INSERT INTO reading_sessions (user_id, story_id, started_at)
            VALUES (?, ?, ?)
            """,
            (user_id, story_id, now_utc_iso()),
        )
        con.commit()
        con.close()

        return jsonify({"ok": True})

    @app.post("/api/complete_book")
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
        story_ids = [s["id"] for s in stories]
        if story_id not in story_ids:
            return jsonify({"ok": False, "error": "Invalid story_id"}), 400

        st = get_state(user_id)
        unlocks = compute_unlocks(st, stories)
        if story_id not in unlocks["unlocked_books"]:
            return jsonify({"ok": False, "error": "Story is locked"}), 403

        story = get_story(story_id)
        word_count = len(story["text"].split()) if story else 0

        # "too fast" rule
        # approx: if book finished quicker than a generous minimum time and user reached most of the content
        estimated_min_time = max(30, int(word_count / 4.0))
        completed_too_fast = reading_time < estimated_min_time and scroll_depth >= 0.8

        suspicious_reasons = []
        if completed_too_fast:
            suspicious_reasons.append("Completed unusually fast")
        if disengaged_windows >= 3:
            suspicious_reasons.append("Several disengaged windows detected")
        if focus_loss_ratio >= 0.35 and reading_time < estimated_min_time * 1.5:
            suspicious_reasons.append("High focus loss during a short session")
        if idle_ratio >= 0.7 and reading_time < estimated_min_time * 1.5:
            suspicious_reasons.append("High idle time before completion")

        suspicious = len(suspicious_reasons) > 0

        con = db()
        latest = con.execute(
            """
            SELECT id
            FROM reading_sessions
            WHERE user_id = ? AND story_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, story_id),
        ).fetchone()

        if latest:
            con.execute(
                """
                UPDATE reading_sessions
                SET completed_at = ?, reading_time_s = ?, scroll_depth = ?, suspicious = ?, suspicious_reason = ?
                WHERE id = ?
                """,
                (
                    now_utc_iso(),
                    reading_time,
                    scroll_depth,
                    1 if suspicious else 0,
                    "; ".join(suspicious_reasons),
                    latest["id"],
                ),
            )
            con.commit()
        con.close()

        if completed_too_fast:
            st["last_engagement_label"] = "disengaged"
            st["last_support_message"] = "That was very quick — let’s do a quick check first 📖"
            save_state(user_id, st)

        should_trigger_quiz = False
        quiz_reason = ""

        if suspicious:
            should_trigger_quiz = True
            quiz_reason = "suspicious"
        elif random.random() < RANDOM_END_QUIZ_CHANCE:
            should_trigger_quiz = True
            quiz_reason = "random_end_check"

        if should_trigger_quiz:
            session["pending_completion"] = {
                "story_id": story_id,
                "reason": quiz_reason,
            }
            return jsonify(
                {
                    "ok": True,
                    "needs_quiz": True,
                    "quiz_url": url_for("quiz_page", story_id=story_id),
                    "reason": quiz_reason,
                    "suspicious_reasons": suspicious_reasons,
                }
            )

        saved = mark_book_complete(user_id, story_id)
        new_unlocks = compute_unlocks(saved, stories)
        return jsonify({"ok": True, "needs_quiz": False, "state": saved, "unlocks": new_unlocks})

    @app.get("/api/quiz/<story_id>")
    def api_quiz(story_id: str):
        story = get_story(story_id)
        if not story:
            return jsonify({"ok": False, "error": "Story not found"}), 404

        quiz = story.get("quiz", [])
        return jsonify({"ok": True, "quiz": quiz, "title": story["title"]})

    @app.post("/api/quiz/<story_id>")
    def api_submit_quiz(story_id: str):
        user_id = ensure_user()
        data = request.get_json(force=True)
        answers = data.get("answers", [])

        story = get_story(story_id)
        if not story:
            return jsonify({"ok": False, "error": "Story not found"}), 404

        quiz = story.get("quiz", [])
        if not quiz:
            return jsonify({"ok": False, "error": "No quiz for this story"}), 400

        score = 0
        for i, q in enumerate(quiz):
            if i < len(answers) and answers[i] == q["answer"]:
                score += 1

        total = len(quiz)
        passed = score >= max(1, total - 1)

        con = db()
        con.execute(
            """
            INSERT INTO quiz_results (user_id, story_id, score, total, passed, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, story_id, score, total, 1 if passed else 0, now_utc_iso()),
        )
        con.commit()
        con.close()

        pending = session.get("pending_completion")
        completion_applied = False

        if pending and pending.get("story_id") == story_id:
            if passed:
                mark_book_complete(user_id, story_id)
                completion_applied = True
            session.pop("pending_completion", None)

        return jsonify(
            {
                "ok": True,
                "score": score,
                "total": total,
                "passed": passed,
                "completion_applied": completion_applied,
            }
        )

    @app.post("/api/select_avatar")
    def api_select_avatar():
        user_id = ensure_user()
        payload = request.get_json(force=True)
        avatar_emoji = str(payload.get("avatar", "")).strip()

        st = get_state(user_id)
        stories = load_stories()
        unlocks = compute_unlocks(st, stories)
        if avatar_emoji not in unlocks["unlocked_avatars"]:
            return jsonify({"ok": False, "error": "Avatar locked"}), 403

        st["selected_avatar"] = avatar_emoji
        add_achievement(st, "Changed Avatar 🎭")
        saved = save_state(user_id, st)
        return jsonify({"ok": True, "state": saved})

    @app.post("/api/select_bg")
    def api_select_bg():
        user_id = ensure_user()
        payload = request.get_json(force=True)
        bg = str(payload.get("bg", "")).strip()

        st = get_state(user_id)
        stories = load_stories()
        unlocks = compute_unlocks(st, stories)
        if bg not in unlocks["unlocked_bgs"]:
            return jsonify({"ok": False, "error": "Background locked"}), 403

        st["selected_bg"] = bg
        add_achievement(st, "Changed Background 🖼️")
        saved = save_state(user_id, st)
        return jsonify({"ok": True, "state": saved})

    @app.post("/api/engagement")
    def api_engagement():
        user_id = ensure_user()
        data = request.get_json(force=True)

        story_id = str(data.get("story_id", "")).strip() or "unknown"

        idle_ratio = float(data.get("idle_ratio", 0.0))
        scroll_speed_px_s = float(data.get("scroll_speed_px_s", 0.0))
        scroll_depth_ratio = float(data.get("scroll_depth_ratio", 0.0))
        focus_loss_ratio = float(data.get("focus_loss_ratio", 0.0))
        nav_rate_per_min = float(data.get("nav_rate_per_min", 0.0))
        interaction_rate_per_min = float(data.get("interaction_rate_per_min", 0.0))

        score, label = fuzzy_engagement(
            idle_ratio=idle_ratio,
            scroll_speed_px_s=scroll_speed_px_s,
            scroll_depth_ratio=scroll_depth_ratio,
            focus_loss_ratio=focus_loss_ratio,
            nav_rate_per_min=nav_rate_per_min,
            interaction_rate_per_min=interaction_rate_per_min,
        )

        if label == "disengaged":
            msg = "Tiny goal: read one more paragraph 💛"
        elif label == "neutral":
            msg = "Nice! Keep going — you’re close to an unlock ⭐"
        else:
            msg = "You’re locked in! 🚀"

        st = get_state(user_id)

        # engaged +1 every 30 seconds
        if label == "engaged":
            st["engaged_streak_windows"] = int(st.get("engaged_streak_windows", 0)) + 1
            if st["engaged_streak_windows"] >= ENGAGED_WINDOWS_FOR_PLUS1:
                st["health"] = clamp(int(st["health"]) + ENGAGED_PLUS, HEALTH_MIN, HEALTH_MAX)
                st["engaged_streak_windows"] = 0
        else:
            st["engaged_streak_windows"] = 0

        # disengaged penalty after 30 seconds
        if label == "disengaged":
            st["disengaged_streak_windows"] = int(st.get("disengaged_streak_windows", 0)) + 1
            if st["disengaged_streak_windows"] >= DISENGAGED_WINDOWS_TRIGGER:
                st["health"] = clamp(int(st["health"]) - DISENGAGED_PENALTY, HEALTH_MIN, HEALTH_MAX)
                st["disengaged_streak_windows"] = 0
        else:
            st["disengaged_streak_windows"] = 0

        # idle cap
        st["idle_streak_windows"] = int(st.get("idle_streak_windows", 0))
        st["idle_penalty_latched"] = int(st.get("idle_penalty_latched", 0))

        if idle_ratio >= IDLE_HIGH:
            st["idle_streak_windows"] += 1
        else:
            st["idle_streak_windows"] = 0

        if st["idle_penalty_latched"] == 0 and st["idle_streak_windows"] >= IDLE_WINDOWS_TRIGGER:
            st["health"] = clamp(int(st["health"]) - IDLE_PENALTY, HEALTH_MIN, HEALTH_MAX)
            st["idle_penalty_latched"] = 1

        if idle_ratio < IDLE_RECOVER:
            st["idle_penalty_latched"] = 0
            st["idle_streak_windows"] = 0

        st["last_engagement_label"] = label
        st["last_engagement_score"] = float(score)
        st["last_support_message"] = msg

        save_state(user_id, st)

        con = db()
        con.execute(
            """
            INSERT INTO engagement_events
            (user_id, ts, story_id, idle_ratio, scroll_speed_px_s, scroll_depth_ratio, focus_loss_ratio,
             nav_rate_per_min, interaction_rate_per_min, score, label)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                now_utc_iso(),
                story_id,
                idle_ratio,
                scroll_speed_px_s,
                scroll_depth_ratio,
                focus_loss_ratio,
                nav_rate_per_min,
                interaction_rate_per_min,
                float(score),
                label,
            ),
        )
        con.commit()
        con.close()

        return jsonify({"score": score, "label": label, "support_message": msg})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)