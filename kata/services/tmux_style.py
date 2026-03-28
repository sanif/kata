"""Apply per-project color styling to tmux sessions.

Uses pane-border-status for a colored accent line, colored pane borders,
and recolors the status bar by reading global format strings and replacing
the background color with the project's color.
"""

import re
import subprocess

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.utils.colors import hex_to_256, resolve_color


def _run_tmux(*args: str) -> str | None:
    """Run a tmux command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _set_window_option(session_name: str, option: str, value: str) -> None:
    """Set a window option on all windows in a session."""
    _run_tmux("set-option", "-w", "-t", session_name, option, value)


def _unset_window_option(session_name: str, option: str) -> None:
    """Unset a window option on a session."""
    _run_tmux("set-option", "-w", "-t", session_name, "-u", option)


def _set_session_option(session_name: str, option: str, value: str) -> None:
    """Set a session option."""
    _run_tmux("set-option", "-t", session_name, option, value)


def _unset_session_option(session_name: str, option: str) -> None:
    """Unset a session option."""
    _run_tmux("set-option", "-t", session_name, "-u", option)


def _get_global_option(option: str) -> str | None:
    """Read a global tmux option value."""
    return _run_tmux("show-options", "-gv", option)


def _get_global_window_option(option: str) -> str | None:
    """Read a global tmux window option value."""
    return _run_tmux("show-window-options", "-gv", option)


def _recolor_format(fmt: str, old_bg: str, color_str: str) -> str:
    """Replace background color references in a tmux format string.

    Replaces both the exact bg= value and bare color references after commas.
    """
    # Replace bg=<old> with bg=<new>
    result = fmt.replace(f"bg={old_bg}", f"bg={color_str}")
    # Replace standalone color after fg=...,<old> patterns (pill separators)
    # e.g. #[fg=#f2cdcd,bg=#1e1e2e] -> #[fg=#f2cdcd,bg=colour176]
    # Also handle cases where old_bg appears as fg for pill-style separators
    # that use the status bg as their fg to create the arrow effect
    result = result.replace(f"fg={old_bg}", f"fg={color_str}")
    return result


def apply_project_color(session_name: str, color: str | None) -> None:
    """Apply project color to a tmux session's styling.

    Enables pane-border-status with a colored accent line, sets pane border
    colors, and recolors the status bar by replacing the global background
    color with the project's color in all format strings.
    No-op if color is None or unresolvable.
    """
    hex_color = resolve_color(color)
    if not hex_color:
        return

    color_256 = hex_to_256(hex_color)
    color_str = f"colour{color_256}"

    # --- Accent line ---
    border_format = (
        f"#[bg={color_str},fg=black,bold] #S #[default]"
        f"#[fg={color_str}]" + "─" * 200 + "#[default]"
    )

    from kata.core.settings import get_settings

    settings = get_settings()
    if settings.color_accent_enabled:
        position = settings.color_accent_position
        _set_window_option(session_name, "pane-border-status", position)
        _set_window_option(session_name, "pane-border-format", border_format)
        _set_window_option(session_name, "pane-border-style", f"fg={color_str}")
        _set_window_option(session_name, "pane-active-border-style", f"fg={color_str}")

    # --- Status bar recolor ---
    # Read global status-style to find the current bg color
    global_style = _get_global_option("status-style") or ""
    bg_match = re.search(r"bg=(#[0-9a-fA-F]{6}|colour\d+)", global_style)
    if not bg_match:
        return

    old_bg = bg_match.group(1)

    # Recolor status-style, preserving original fg
    fg_match = re.search(r"fg=(#[0-9a-fA-F]{6}|colour\d+)", global_style)
    orig_fg = fg_match.group(1) if fg_match else "#585b70"
    _set_session_option(session_name, "status-style", f"bg={color_str},fg={orig_fg}")

    # Recolor format strings that hardcode the bg color
    for opt, getter in [
        ("status-left", _get_global_option),
        ("status-right", _get_global_option),
    ]:
        fmt = getter(opt)
        if fmt:
            _set_session_option(session_name, opt, _recolor_format(fmt, old_bg, color_str))

    for opt in ("window-status-format", "window-status-current-format"):
        fmt = _get_global_window_option(opt)
        if fmt:
            _set_window_option(session_name, opt, _recolor_format(fmt, old_bg, color_str))


def clear_project_color(session_name: str) -> None:
    """Reset tmux session styling to defaults."""
    # Accent line
    _unset_window_option(session_name, "pane-border-status")
    _unset_window_option(session_name, "pane-border-format")
    _unset_window_option(session_name, "pane-border-style")
    _unset_window_option(session_name, "pane-active-border-style")

    # Status bar
    _unset_session_option(session_name, "status-style")
    _unset_session_option(session_name, "status-left")
    _unset_session_option(session_name, "status-right")
    _unset_window_option(session_name, "window-status-format")
    _unset_window_option(session_name, "window-status-current-format")
