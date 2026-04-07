import json

from config import STORIES_PATH


def load_stories() -> list[dict]:
    """Load all stories from stories.json."""
    with open(STORIES_PATH, "r", encoding="utf-8") as story_file:
        return json.load(story_file)


def get_story(story_id: str) -> dict | None:
    """Return one story by id, or None if not found."""
    for story in load_stories():
        if story["id"] == story_id:
            return story
    return None


def compute_unlocks(state: dict, stories: list[dict]) -> dict:
    """
    Work out which books, avatars, and backgrounds are unlocked.
    """
    completed_books = set(state["completed_books"])
    story_ids = [story["id"] for story in stories]

    # -----------------------------
    # Book unlocks
    # -----------------------------
    unlocked_books = []
    for index, story_id in enumerate(story_ids):
        if index == 0:
            unlocked_books.append(story_id)
        else:
            previous_story_id = story_ids[index - 1]
            if previous_story_id in completed_books:
                unlocked_books.append(story_id)

    # -----------------------------
    # Avatar unlocks
    # Default avatar is separate and always shown as fallback.
    # Trainer avatars both unlock after Book 1.
    # -----------------------------
    unlocked_avatars = []

    if "book1" in completed_books:
        unlocked_avatars.extend(["blueTrainer", "blondeTrainer"])

    # -----------------------------
    # Background unlocks
    # -----------------------------
    unlocked_backgrounds = ["bg-default"]

    if "book2" in completed_books:
        unlocked_backgrounds.append("bg-space")

    if "book3" in completed_books:
        unlocked_backgrounds.append("bg-forest")

    return {
        "unlocked_books": unlocked_books,
        "unlocked_avatars": unlocked_avatars,
        "unlocked_bgs": unlocked_backgrounds,
    }