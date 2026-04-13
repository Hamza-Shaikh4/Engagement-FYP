import json
from collections import defaultdict

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


def group_stories_by_stage(stories: list[dict]) -> dict[int, list[dict]]:
    """Group stories by stage number."""
    grouped = defaultdict(list)
    for story in stories:
        grouped[int(story.get("stage", 1))].append(story)
    return dict(sorted(grouped.items()))


def compute_unlocks(state: dict, stories: list[dict]) -> dict:
    """
    Work out which books, avatars, and backgrounds are unlocked.

    Rules:
    - Stage 1 is unlocked by default.
    - A later stage unlocks only when all books in the previous stage are completed.
    - All books inside an unlocked stage are available.
    - Trainer avatars unlock after book 1.
    - Backgrounds unlock after whole stages are completed.
    """
    completed_books = set(state["completed_books"])
    grouped = group_stories_by_stage(stories)

    unlocked_books = []
    unlocked_stages = []
    completed_stages = []

    previous_stage_completed = True

    for stage_number, stage_stories in grouped.items():
        stage_story_ids = [story["id"] for story in stage_stories]
        stage_completed = all(story_id in completed_books for story_id in stage_story_ids)

        if stage_completed:
            completed_stages.append(stage_number)

        if stage_number == 1 or previous_stage_completed:
            unlocked_stages.append(stage_number)
            unlocked_books.extend(stage_story_ids)

        previous_stage_completed = stage_completed

    unlocked_avatars = []
    if "book1" in completed_books:
        unlocked_avatars.extend(["blueTrainer", "blondeTrainer"])

    # Backgrounds now unlock by completed stage
    unlocked_backgrounds = ["bg-default"]

    if 1 in completed_stages:
        unlocked_backgrounds.append("bg-space")

    if 2 in completed_stages:
        unlocked_backgrounds.append("bg-forest")

    return {
        "unlocked_books": unlocked_books,
        "unlocked_stages": unlocked_stages,
        "completed_stages": completed_stages,
        "unlocked_avatars": unlocked_avatars,
        "unlocked_bgs": unlocked_backgrounds,
    }