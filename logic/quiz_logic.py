"""This file checks quiz answers and flags suspicious reading sessions."""

from config import (
    RANDOM_END_QUIZ_CHANCE,
    MIN_SCROLL_DEPTH_FOR_FAST_FINISH,
    HIGH_FOCUS_LOSS_THRESHOLD,
    HIGH_IDLE_THRESHOLD,
)

# Estimate the shortest normal reading time for a story.
def estimate_min_reading_time_seconds(story_text: str) -> int:

    word_count = len(story_text.split())
    return max(30, int(word_count / 4.0))

# List the reasons why a reading session looks suspicious.
def get_suspicious_reasons(
    story_text: str,
    reading_time: float,
    scroll_depth: float,
    disengaged_windows: int,
    focus_loss_ratio: float,
    idle_ratio: float,
) -> list[str]:

    reasons = []
    min_time = estimate_min_reading_time_seconds(story_text)

    completed_too_fast = (
        reading_time < min_time and scroll_depth >= MIN_SCROLL_DEPTH_FOR_FAST_FINISH
    )

    if completed_too_fast:
        reasons.append("Completed unusually fast")

    if disengaged_windows >= 3:
        reasons.append("Several disengaged windows detected")

    if focus_loss_ratio >= HIGH_FOCUS_LOSS_THRESHOLD and reading_time < min_time * 1.5:
        reasons.append("High focus loss during a short session")

    if idle_ratio >= HIGH_IDLE_THRESHOLD and reading_time < min_time * 1.5:
        reasons.append("High idle time before completion")

    return reasons

#  Decide if a end quiz should appear.
def should_trigger_random_end_quiz(random_value: float) -> bool:
    return random_value < RANDOM_END_QUIZ_CHANCE

# Grade the quiz answers and determine if the user passed.
def grade_quiz(quiz: list[dict], answers: list[int]) -> tuple[int, int, bool]:

    score = 0

    for question_index, question in enumerate(quiz):
        if question_index < len(answers) and answers[question_index] == question["answer"]:
            score += 1

    total = len(quiz)
    passed = score >= max(1, total - 1)
    return score, total, passed