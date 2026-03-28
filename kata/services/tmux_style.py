"""Apply per-project color styling to tmux sessions.

Uses pane-border-status top for a colored accent line at the top of each pane,
plus colored pane borders. The status bar is left untouched to avoid conflicting
with the user's custom tmux status bar configuration.
"""

import subprocess

from kata.utils.colors import hex_to_256, resolve_color


def _set_window_option(session_name: str, option: str, value: str) -> None:
    """Set a window option on all windows in a session."""
    try:
        subprocess.run(
            ["tmux", "set-option", "-w", "-t", session_name, option, value],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _unset_window_option(session_name: str, option: str) -> None:
    """Unset a window option on a session."""
    try:
        subprocess.run(
            ["tmux", "set-option", "-w", "-t", session_name, "-u", option],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def apply_project_color(session_name: str, color: str | None) -> None:
    """Apply project color to a tmux session's styling.

    Enables pane-border-status at top with a colored format line,
    and sets pane border colors. Visible even with a single pane.
    No-op if color is None or unresolvable.
    """
    hex_color = resolve_color(color)
    if not hex_color:
        return

    color_256 = hex_to_256(hex_color)
    color_str = f"colour{color_256}"

    border_format = (
        f"#[bg={color_str},fg=black,bold] #S #[default]"
        f"#[fg={color_str}]" + "─" * 200 + "#[default]"
    )

    _set_window_option(session_name, "pane-border-status", "top")
    _set_window_option(session_name, "pane-border-format", border_format)
    _set_window_option(session_name, "pane-border-style", f"fg={color_str}")
    _set_window_option(session_name, "pane-active-border-style", f"fg={color_str}")


def clear_project_color(session_name: str) -> None:
    """Reset tmux session styling to defaults."""
    _unset_window_option(session_name, "pane-border-status")
    _unset_window_option(session_name, "pane-border-format")
    _unset_window_option(session_name, "pane-border-style")
    _unset_window_option(session_name, "pane-active-border-style")
