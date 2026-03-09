"""Lightweight project switcher strip for tmux overlay panes."""

import sys
import termios
import tty

from rich.console import Console
from rich.text import Text

from kata.core.models import SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import (
    get_all_session_statuses,
    get_current_tmux_session,
    launch_or_attach,
)
from kata.utils.paths import sanitize_session_name


def render_strip(projects, statuses, selected_index, current_session=None) -> Text:
    """Render the project strip as a Rich Text object."""
    text = Text()
    text.append("  ")
    for i, project in enumerate(projects):
        sname = sanitize_session_name(project.name)
        status = statuses.get(sname, SessionStatus.IDLE)
        dot_style = {
            SessionStatus.ACTIVE: "green",
            SessionStatus.DETACHED: "yellow",
            SessionStatus.IDLE: "dim",
        }[status]

        if i > 0:
            text.append("   ")

        if i == selected_index:
            text.append(f" ● {project.name} ", "bold reverse")
        elif current_session and (project.name == current_session or sname == current_session):
            text.append(f" ● {project.name} ", "dim")
        else:
            text.append(f" ● {project.name} ", dot_style)
    text.append("  ")
    return text


def _read_key() -> str:
    """Read a single keypress in raw terminal mode."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            return "escape"
        elif ch in ("\r", "\n"):
            return "enter"
        elif ch == " ":
            return "space"
        elif ch == "\x03":
            return "escape"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_switch_strip(limit: int = 5) -> None:
    """Run the interactive switch strip."""
    console = Console()
    registry = get_registry()
    registry.reload()

    current = get_current_tmux_session()
    projects = registry.get_recent_projects(limit=limit, current_session=current)

    if not projects:
        console.print("[dim]No projects registered.[/dim]")
        return

    statuses = get_all_session_statuses()
    selected = 0

    selected_project = None
    try:
        while True:
            console.clear()
            strip = render_strip(projects, statuses, selected, current)
            console.print()
            console.print(strip, justify="center")
            console.print(
                "[dim]Space[/dim] cycle  [dim]Enter[/dim] switch  [dim]Esc[/dim] cancel",
                justify="center",
            )

            key = _read_key()
            if key == "space":
                selected = (selected + 1) % len(projects)
            elif key == "enter":
                selected_project = projects[selected]
                break
            elif key == "escape":
                break
    finally:
        console.clear()

    if selected_project:
        selected_project.record_open()
        registry.update(selected_project)
        launch_or_attach(selected_project)
