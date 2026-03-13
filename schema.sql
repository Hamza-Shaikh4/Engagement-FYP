CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    story_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);