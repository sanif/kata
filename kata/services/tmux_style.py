"""Apply per-project color styling to tmux sessions."""

import subprocess

from kata.utils.colors import hex_to_256, resolve_color


def apply_project_color(session_name: str, color: str | None) -> None:
    """Apply project color to a tmux session's styling.

    Sets pane border colors and status-left segment background.
    No-op if color is None or unresolvable.
    """
    hex_color = resolve_color(color)
    if not hex_color:
        return

    color_256 = hex_to_256(hex_color)
    color_str = f"colour{color_256}"

    cmds = [
        ["tmux", "set", "-t", session_name, "pane-border-style", f"fg={color_str}"],
        ["tmux", "set", "-t", session_name, "pane-active-border-style", f"fg={color_str}"],
        [
            "tmux",
            "set",
            "-t",
            session_name,
            "status-left",
            f"#[bg={color_str},fg=black,bold] #S #[default] ",
        ],
    ]

    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


def clear_project_color(session_name: str) -> None:
    """Reset tmux session styling to defaults."""
    cmds = [
        ["tmux", "set", "-t", session_name, "-u", "pane-border-style"],
        ["tmux", "set", "-t", session_name, "-u", "pane-active-border-style"],
        ["tmux", "set", "-t", session_name, "-u", "status-left"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
