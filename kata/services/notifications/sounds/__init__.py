"""Bundled notification sound files."""

from pathlib import Path

SOUNDS_DIR = Path(__file__).parent

# Default sound mapping: notification type value → filename
DEFAULT_SOUNDS: dict[str, str] = {
    "task_complete": "task-complete.mp3",
    "review_done": "review-complete.mp3",
    "question": "question.mp3",
    "plan_ready": "plan-ready.mp3",
    "error": "error.mp3",
    "session_limit": "error.mp3",
}


def get_sound_path(filename: str) -> Path | None:
    """Resolve a sound filename to its full path. Returns None if not found."""
    path = SOUNDS_DIR / filename
    return path if path.exists() else None
