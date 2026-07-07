"""Layout parsing and rendering helpers for tmuxp window/pane structure."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PaneInfo:
    """Information about a tmux pane."""

    commands: list[str]
    layout: str = "single"


@dataclass
class WindowInfo:
    """Information about a tmux window."""

    name: str
    panes: list[PaneInfo]
    layout: str = "tiled"


@dataclass
class LayoutInfo:
    """Parsed layout information from tmuxp config."""

    session_name: str
    windows: list[WindowInfo]
    start_directory: str = ""


def parse_tmuxp_config(config_path: Path) -> LayoutInfo | None:
    """Parse a tmuxp YAML config file.

    Args:
        config_path: Path to the tmuxp YAML config

    Returns:
        LayoutInfo with parsed structure, or None if parsing fails
    """
    if not config_path.exists():
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or not isinstance(config, dict):
            return None

        session_name = config.get("session_name", "unnamed")
        start_directory = config.get("start_directory", "")
        windows = []

        for window_data in config.get("windows", []):
            if not isinstance(window_data, dict):
                continue

            window_name = window_data.get("window_name", "unnamed")
            window_layout = window_data.get("layout", "tiled")
            panes = []

            panes_data = window_data.get("panes", [])
            if isinstance(panes_data, list):
                for pane_data in panes_data:
                    commands = []
                    if isinstance(pane_data, dict):
                        shell_cmd = pane_data.get("shell_command", [])
                        if isinstance(shell_cmd, list):
                            commands = [c for c in shell_cmd if c and not c.strip().startswith("#")]
                        elif isinstance(shell_cmd, str):
                            if not shell_cmd.strip().startswith("#"):
                                commands = [shell_cmd]
                    elif isinstance(pane_data, str):
                        if not pane_data.strip().startswith("#"):
                            commands = [pane_data]

                    panes.append(PaneInfo(commands=commands))

            # Ensure at least one pane
            if not panes:
                panes.append(PaneInfo(commands=[]))

            windows.append(WindowInfo(name=window_name, panes=panes, layout=window_layout))

        return LayoutInfo(
            session_name=session_name,
            windows=windows,
            start_directory=start_directory,
        )

    except (OSError, yaml.YAMLError, KeyError):
        return None


def render_window_diagram(window: WindowInfo, width: int = 30) -> list[str]:
    """Render a single window as ASCII art.

    Args:
        window: Window information to render
        width: Width of the diagram

    Returns:
        List of lines representing the window
    """
    lines = []
    inner_width = width - 2

    # Window header
    title = f" {window.name} "
    if len(title) > inner_width - 2:
        title = title[: inner_width - 5] + "... "
    padding = inner_width - len(title)
    left_pad = padding // 2
    right_pad = padding - left_pad

    lines.append("┌" + "─" * inner_width + "┐")
    lines.append("│" + " " * left_pad + title + " " * right_pad + "│")
    lines.append("├" + "─" * inner_width + "┤")

    # Panes
    num_panes = len(window.panes)
    if num_panes == 1:
        # Single pane
        pane = window.panes[0]
        cmd_display = _get_command_display(pane.commands, inner_width - 2)
        lines.append("│ " + cmd_display.ljust(inner_width - 2) + " │")
    elif num_panes == 2:
        # Two panes side by side or stacked based on layout
        half_width = (inner_width - 3) // 2
        p1_cmd = _get_command_display(window.panes[0].commands, half_width)
        p2_cmd = _get_command_display(window.panes[1].commands, half_width)

        if window.layout in ("main-vertical", "even-horizontal"):
            # Side by side
            lines.append("│ " + p1_cmd.ljust(half_width) + "│" + p2_cmd.ljust(half_width) + " │")
        else:
            # Stacked
            lines.append("│ " + p1_cmd.ljust(inner_width - 2) + " │")
            lines.append("├" + "─" * inner_width + "┤")
            lines.append("│ " + p2_cmd.ljust(inner_width - 2) + " │")
    else:
        # Multiple panes - show count
        for i, pane in enumerate(window.panes[:3]):  # Show max 3
            cmd_display = _get_command_display(pane.commands, inner_width - 4)
            lines.append(f"│ {i + 1}. {cmd_display.ljust(inner_width - 5)}│")

        if num_panes > 3:
            lines.append(f"│ ... +{num_panes - 3} more".ljust(inner_width) + " │")

    lines.append("└" + "─" * inner_width + "┘")

    return lines


def _get_command_display(commands: list[str], max_width: int) -> str:
    """Get display string for pane commands.

    Args:
        commands: List of commands
        max_width: Maximum display width

    Returns:
        Formatted command string
    """
    if not commands:
        return "[shell]"

    # Get first non-empty, non-comment command
    for cmd in commands:
        cmd = cmd.strip()
        if cmd and not cmd.startswith("#"):
            if len(cmd) > max_width:
                return cmd[: max_width - 3] + "..."
            return cmd

    return "[shell]"


def render_layout_diagram(layout: LayoutInfo, max_width: int = 40) -> str:
    """Render complete layout as ASCII diagram.

    Args:
        layout: Layout information
        max_width: Maximum width for each window diagram

    Returns:
        Multi-line string with the complete diagram
    """
    if not layout.windows:
        return "[dim]No windows defined[/dim]"

    lines = []
    window_width = min(max_width, 35)

    for i, window in enumerate(layout.windows):
        window_lines = render_window_diagram(window, window_width)
        lines.extend(window_lines)

        # Add spacing between windows
        if i < len(layout.windows) - 1:
            lines.append("")

    return "\n".join(lines)


def render_layout_summary(layout: LayoutInfo) -> str:
    """Render a compact layout summary with Rich markup.

    Args:
        layout: Layout information

    Returns:
        Formatted summary string
    """
    if not layout.windows:
        return "[dim]No layout configured[/dim]"

    parts = []
    for window in layout.windows:
        pane_count = len(window.panes)
        pane_text = "pane" if pane_count == 1 else "panes"
        parts.append(f"[$primary]{window.name}[/$primary] ({pane_count} {pane_text})")

    return " → ".join(parts)
