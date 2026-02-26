"""Terminal window focus/activation for macOS."""

from __future__ import annotations

import logging
import os
import subprocess

from kata.core.settings import get_settings

logger = logging.getLogger(__name__)

# Known terminal app bundle IDs
TERMINAL_APPS = {
    "wezterm": "com.github.wez.wezterm",
    "iterm2": "com.googlecode.iterm2",
    "terminal": "com.apple.Terminal",
    "kitty": "net.kovidgoyal.kitty",
    "alacritty": "org.alacritty",
    "ghostty": "com.mitchellh.ghostty",
    "warp": "dev.warp.Warp-Stable",
}


def _detect_terminal_app() -> str | None:
    """Detect the current terminal application."""
    # Check TERM_PROGRAM environment variable
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program:
        for name in TERMINAL_APPS:
            if name in term_program:
                return TERMINAL_APPS[name]

    # Check common env vars
    if os.environ.get("WEZTERM_PANE"):
        return TERMINAL_APPS["wezterm"]
    if os.environ.get("ITERM_SESSION_ID"):
        return TERMINAL_APPS["iterm2"]
    if os.environ.get("KITTY_PID"):
        return TERMINAL_APPS["kitty"]

    return None


def focus_terminal() -> bool:
    """Bring the terminal window to front.

    Returns True if successful.
    """
    settings = get_settings()
    terminal_setting = settings.notifications_terminal_app

    if terminal_setting == "auto":
        bundle_id = _detect_terminal_app()
    else:
        bundle_id = TERMINAL_APPS.get(terminal_setting.lower())
        if not bundle_id:
            # Treat the setting as a direct bundle ID
            bundle_id = terminal_setting

    if not bundle_id:
        logger.debug("Could not determine terminal app for focus")
        return False

    try:
        script = f'tell application id "{bundle_id}" to activate'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        logger.debug("Failed to focus terminal", exc_info=True)
        return False


def switch_to_session(session_name: str) -> bool:
    """Switch tmux to the given session and bring terminal to front.

    Returns True if successful.
    """
    try:
        result = subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False
        return focus_terminal()
    except Exception:
        logger.debug("Failed to switch session", exc_info=True)
        return False
