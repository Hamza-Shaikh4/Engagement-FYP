from pathlib import Path

# Base folder of the project
BASE_DIR = Path(__file__).resolve().parent

# Flask
SECRET_KEY = "dev-secret-key"

# Files
DB_PATH = BASE_DIR / "app.db"
STORIES_PATH = BASE_DIR / "static" / "stories.json"
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Health / gamification rules
HEALTH_MIN = 30
HEALTH_MAX = 100

ENGAGED_WINDOWS_FOR_PLUS1 = 3
ENGAGED_HEALTH_BONUS = 1

DISENGAGED_WINDOWS_TRIGGER = 3
DISENGAGED_HEALTH_PENALTY = 2

IDLE_HIGH_THRESHOLD = 0.85
IDLE_RECOVER_THRESHOLD = 0.40
IDLE_WINDOWS_TRIGGER = 3
IDLE_HEALTH_PENALTY = 2

INACTIVITY_DAYS_TRIGGER = 2
INACTIVITY_HEALTH_PENALTY = 5

# Quiz / suspicious reading rules
RANDOM_END_QUIZ_CHANCE = 1.0
MIN_SCROLL_DEPTH_FOR_FAST_FINISH = 0.8
HIGH_FOCUS_LOSS_THRESHOLD = 0.20
FAST_SCROLL_BURSTS_THRESHOLD = 3
HIGH_IDLE_THRESHOLD = 0.7

# How much health to restore when a book is completed 
BOOK_COMPLETION_HEALTH_RESTORE = 20     

# Model selection
ENGAGEMENT_MODEL_NAME = "hmm"   # change models between "hmm" and "fuzzy"