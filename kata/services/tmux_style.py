"""Apply per-project color styling to tmux sessions.

Uses pane-border-status to show a thin colored line at the top of each pane.
This is visible even with a single pane, unlike regular pane borders.
"""

import subprocess

from kata.utils.colors import hex_to_256, resolve_color


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

    cmds = [
        # Show border status line at top of each pane
        ["tmux", "set", "-t", session_name, "pane-border-status", "top"],
        # Format the top line as a colored bar with session name
        [
            "tmux",
            "set",
            "-t",
            session_name,
            "pane-border-format",
            f"#[bg={color_str},fg=black,bold] #S #[default]#[fg={color_str}]"
            + "─" * 200
            + "#[default]",
        ],
        # Color the pane borders themselves
        ["tmux", "set", "-t", session_name, "pane-border-style", f"fg={color_str}"],
        [
            "tmux",
            "set",
            "-t",
            session_name,
            "pane-active-border-style",
            f"fg={color_str}",
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
        ["tmux", "set", "-t", session_name, "-u", "pane-border-status"],
        ["tmux", "set", "-t", session_name, "-u", "pane-border-format"],
        ["tmux", "set", "-t", session_name, "-u", "pane-border-style"],
        ["tmux", "set", "-t", session_name, "-u", "pane-active-border-style"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
