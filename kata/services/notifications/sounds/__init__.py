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

# Available sound packs — each pack has its own subdirectory
# except "default" which uses the root sounds directory.
AVAILABLE_SOUND_PACKS: dict[str, str] = {
    "default": "Default",
    "gentle": "Gentle",
    "arcade": "Arcade",
}


def get_sound_path(filename: str, pack: str = "default") -> Path | None:
    """Resolve a sound filename to its full path for a given pack.

    Returns None if not found.
    """
    if pack == "default":
        path = SOUNDS_DIR / filename
    else:
        path = SOUNDS_DIR / pack / filename
    return path if path.exists() else None
