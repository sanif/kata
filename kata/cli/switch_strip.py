"""Project switcher for tmux overlay panes.

Behaves like Alt+Tab:
  Ctrl+Space        → open & cycle forward
  Ctrl+Shift+Space  → open & cycle backward
  Enter / Space     → switch to selected
  Esc               → cancel

Only shows projects with active or detached tmux sessions.

Architecture:
  tmux binding → `kata switch-strip` (calculates size, spawns popup)
               → `kata switch-strip --popup` (interactive UI inside popup)
"""

import os
import subprocess
import sys
import termios
import tty

from rich.console import Console
from rich.text import Text

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import (
    get_all_session_statuses,
    get_current_tmux_session,
)
from kata.utils.colors import resolve_color
from kata.utils.paths import sanitize_session_name


def _tmux_session_exists(session_name: str) -> bool:
    """Check if a tmux session exists using direct subprocess."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _switch_to_session(project, registry) -> None:
    """Switch to a project's tmux session, launching if needed."""
    from kata.core.config import get_project_config_path, migrate_project_config
    from kata.services.tmux_style import apply_project_color

    session_name = sanitize_session_name(project.name)

    if _tmux_session_exists(session_name):
        apply_project_color(session_name, getattr(project, "color", None))
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            capture_output=True,
        )
    else:
        migrate_project_config(project.name, project.path)
        config_path = get_project_config_path(project.path)
        if config_path.exists():
            subprocess.run(
                ["tmuxp", "load", "-d", str(config_path)],
                capture_output=True,
            )
            import time

            for _ in range(20):
                if _tmux_session_exists(session_name):
                    apply_project_color(session_name, getattr(project, "color", None))
                    subprocess.run(
                        ["tmux", "switch-client", "-t", session_name],
                        capture_output=True,
                    )
                    break
                time.sleep(0.1)

    project.record_open()
    registry.update(project)


def _get_active_projects(registry, statuses, current_session):
    """Get projects that have an active or detached tmux session."""
    all_projects = registry.get_recent_projects(limit=999, current_session=current_session)
    active = []
    for p in all_projects:
        sname = sanitize_session_name(p.name)
        status = statuses.get(sname, SessionStatus.IDLE)
        if status in (SessionStatus.ACTIVE, SessionStatus.DETACHED):
            active.append(p)
    return active


# ── Rendering ────────────────────────────────────────────────────────────

_STATUS = {
    SessionStatus.ACTIVE: ("●", "green"),
    SessionStatus.DETACHED: ("●", "yellow"),
    SessionStatus.IDLE: ("○", "bright_black"),
}


def _content_row(content: Text, width: int) -> Text:
    """Wrap content in box side borders, padding to full width."""
    plain_len = len(content.plain)
    pad = max(0, width - 4 - plain_len)
    t = Text()
    t.append("│ ", "dim")
    t.append_text(content)
    t.append(" " * pad)
    t.append(" │", "dim")
    return t


def render_panel(
    projects, statuses, selected_index, current_session=None, term_width: int = 40
) -> list[Text]:
    """Render the switcher as a bordered panel."""
    w = term_width
    lines: list[Text] = []

    # ── Top border with title ──
    title = " switch "
    side_len = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side_len, "dim")
    top.append(title, "bold cyan")
    top.append("─" * (w - 2 - side_len - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    # ── Spacer ──
    lines.append(_content_row(Text(""), w))

    # ── Project rows ──
    for i, project in enumerate(projects):
        sname = sanitize_session_name(project.name)
        status = statuses.get(sname, SessionStatus.IDLE)
        dot_char, dot_color = _STATUS[status]
        is_current = current_session and (
            project.name == current_session or sname == current_session
        )
        project_color = resolve_color(getattr(project, "color", None))

        entry = Text()
        avail = w - 4
        if i == selected_index:
            inner = Text()
            if project_color:
                inner.append("┃", project_color)
            else:
                inner.append("┃", "cyan")
            inner.append(" ")
            inner.append(dot_char, dot_color)
            inner.append(f" {project.name}", "bold")
            fill = max(0, avail - len(inner.plain))
            inner.append(" " * fill)
            inner.stylize("on grey23")
            entry.append_text(inner)
        elif is_current:
            if project_color:
                entry.append("┃", project_color)
            else:
                entry.append(" ")
            entry.append(" ")
            entry.append(dot_char, dot_color)
            entry.append(f" {project.name}", "dim")
            entry.append("  ‹", "dim cyan")
        else:
            if project_color:
                entry.append("┃", project_color)
            else:
                entry.append(" ")
            entry.append(" ")
            entry.append(dot_char, dot_color)
            entry.append(f" {project.name}")

        lines.append(_content_row(entry, w))

    # ── Spacer ──
    lines.append(_content_row(Text(""), w))

    # ── Separator ──
    sep = Text()
    sep.append("├", "dim")
    sep.append("─" * (w - 2), "dim")
    sep.append("┤", "dim")
    lines.append(sep)

    # ── Hint bar ──
    hint = Text()
    hint.append("  C-␣", "cyan")
    hint.append(" next", "dim")
    hint.append("   ↵/␣", "cyan")
    hint.append(" go", "dim")
    hint.append("   esc", "cyan")
    hint.append(" quit", "dim")
    hint_len = len(hint.plain)
    avail = w - 4
    left_pad = max(0, (avail - hint_len) // 2)
    centered_hint = Text()
    centered_hint.append(" " * left_pad)
    centered_hint.append_text(hint)
    lines.append(_content_row(centered_hint, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


def _calc_popup_size(projects):
    """Calculate the ideal popup width and height for the project list."""
    max_name_len = max(len(p.name) for p in projects) if projects else 10
    # "│ " (2) + "┃" (1) + " " (1) + dot (1) + " " (1) + name + pad + " │" (2)
    # Also need room for hint bar: "  C-␣ next   ↵ go   esc quit" = 29 chars + borders
    hint_w = 37  # hint text + border chrome
    w = max(hint_w, max_name_len + 16)
    # top(1) + spacer(1) + projects(N) + spacer(1) + sep(1) + hint(1) + bottom(1)
    h = len(projects) + 6
    return w, h


# Keep for backward compatibility with tests
def render_strip(
    projects, statuses, selected_index, current_session=None, term_width: int = 80
) -> Text:
    """Render the project strip as a Rich Text object (horizontal)."""
    n = len(projects)
    if n > 0:
        available = term_width - 4
        per_project = available // n - 7
        max_name = max(8, min(20, per_project))
    else:
        max_name = 20

    text = Text()
    for i, project in enumerate(projects):
        sname = sanitize_session_name(project.name)
        status = statuses.get(sname, SessionStatus.IDLE)
        dot_char, dot_color = _STATUS[status]

        if i > 0:
            text.append("  │  ", "dim")

        display_name = project.name[:max_name]
        is_current = current_session and (
            project.name == current_session or sname == current_session
        )

        if i == selected_index:
            text.append(f" {dot_char} ", f"bold {dot_color}")
            text.append(display_name, "bold reverse")
            text.append(" ", "bold reverse")
        elif is_current:
            text.append(f" {dot_char} ", dot_color)
            text.append(display_name, "dim italic")
            text.append(" ")
        else:
            text.append(f" {dot_char} ", dot_color)
            text.append(display_name)
            text.append(" ")

    return text


# ── Input ────────────────────────────────────────────────────────────────


def _read_key() -> str:
    """Read a single keypress in raw terminal mode, blocking."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b"\x00":
            return "ctrl+space"
        elif ch == b"\x1b":
            import select as _sel

            # Read rest of escape sequence — be generous with timeout
            r, _, _ = _sel.select([fd], [], [], 0.1)
            if r:
                seq = os.read(fd, 8)  # read all available bytes at once
                if seq == b"[A":
                    return "up"
                elif seq == b"[B":
                    return "down"
                elif seq == b"[C":
                    return "right"
                elif seq == b"[D":
                    return "left"
                elif seq == b"[Z":
                    return "shift+tab"
                elif seq.startswith(b"O"):
                    # SS3 arrow keys (some terminals)
                    if seq == b"OA":
                        return "up"
                    elif seq == b"OB":
                        return "down"
                # Unknown escape sequence — treat as escape
                return "escape"
            return "escape"
        elif ch in (b"\r", b"\n"):
            return "enter"
        elif ch == b" ":
            return "space"
        elif ch == b"\t":
            return "tab"
        elif ch == b"\x03":
            return "escape"
        return ch.decode("utf-8", errors="replace")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Popup launcher ──────────────────────────────────────────────────────


def open_switcher_popup(backward: bool = False) -> None:
    """Calculate content size and spawn a fitted tmux popup."""
    registry = get_registry()
    registry.reload()

    current = get_current_tmux_session()
    statuses = get_all_session_statuses()
    projects = _get_active_projects(registry, statuses, current)

    if not projects:
        return

    w, h = _calc_popup_size(projects)

    # pane-border-status steals 1 row from the popup content area
    # Check if any project color is set (which enables pane-border-status)
    current_project = None
    if current:
        for p in projects:
            sname = sanitize_session_name(p.name)
            if p.name == current or sname == current:
                current_project = p
                break
    if current_project and getattr(current_project, "color", None):
        h += 1

    cmd = "kata switch-strip --popup"
    if backward:
        cmd += " --backward"

    subprocess.run(
        ["tmux", "display-popup", "-E", "-B", "-w", str(w), "-h", str(h), cmd],
    )


# ── Main loop ────────────────────────────────────────────────────────────


def run_switch_strip(backward: bool = False) -> None:
    """Run the interactive project switcher inside the popup.

    Args:
        backward: If True, start cycling from the end.
    """
    console = Console()
    registry = get_registry()
    registry.reload()

    current = get_current_tmux_session()
    statuses = get_all_session_statuses()
    projects = _get_active_projects(registry, statuses, current)

    if not projects:
        console.print("[dim]No active sessions.[/dim]")
        return

    selected = 0 if not backward else len(projects) - 1
    confirmed = False

    try:
        while True:
            console.clear()
            panel = render_panel(projects, statuses, selected, current, console.width)
            for i, line in enumerate(panel):
                if i < len(panel) - 1:
                    console.print(line)
                else:
                    console.print(line, end="")

            key = _read_key()

            if key in ("ctrl+space", "down", "tab"):
                selected = (selected + 1) % len(projects)
            elif key in ("up", "shift+tab"):
                selected = (selected - 1) % len(projects)
            elif key in ("enter", "space"):
                confirmed = True
                break
            elif key == "escape":
                break
    finally:
        console.clear()

    if confirmed:
        _switch_to_session(projects[selected], registry)
