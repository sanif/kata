"""Audio playback for notification sounds via macOS afplay."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from kata.services.notifications.sounds import DEFAULT_SOUNDS, get_sound_path

logger = logging.getLogger(__name__)


def volume_to_afplay(volume: float) -> float:
    """Convert 0.0-1.0 volume to afplay's scale (1.0 = system volume)."""
    return max(0.0, min(1.0, volume))


def resolve_sound_path(
    notification_type: str,
    overrides: dict[str, str],
    pack: str = "default",
) -> Path | None:
    """Resolve a notification type to a sound file path.

    Checks user overrides first, then falls back to bundled defaults
    for the given sound pack.
    Returns None if no sound is configured for this type.
    """
    if notification_type in overrides:
        override_path = Path(overrides[notification_type])
        if override_path.exists():
            return override_path
        logger.debug(f"Override sound not found: {override_path}, falling back to bundled")

    filename = DEFAULT_SOUNDS.get(notification_type)
    if not filename:
        return None
    return get_sound_path(filename, pack=pack)


def play_sound(sound_path: Path, volume: float = 1.0) -> None:
    """Play a sound file via afplay (non-blocking, fire-and-forget)."""
    if not sound_path.exists():
        return

    afplay_vol = volume_to_afplay(volume)
    try:
        subprocess.Popen(
            ["afplay", "-v", str(afplay_vol), str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        logger.debug("Failed to play sound via afplay", exc_info=True)
