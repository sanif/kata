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

import subprocess
import sys

from rich.text import Text

from kata.cli._termui import (
    FrameRenderer,
    content_row,
    guard_tty,
    raw_screen,
    read_key,
)
from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import (
    get_all_session_statuses,
    get_current_tmux_session,
)
from kata.utils.colors import resolve_color
from kata.utils.paths import sanitize_session_name


def _display_message(msg: str) -> None:
    """Surface a one-line status in the tmux status bar.

    The popup launchers are invoked via ``run-shell`` where stdout is invisible,
    so a bare ``print`` would make the keybinding look dead when a precondition
    (no sessions / not a git repo) is not met.
    """
    try:
        subprocess.run(
            ["tmux", "display-message", msg],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


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
    lines.append(content_row(Text(""), w))

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

        lines.append(content_row(entry, w))

    # ── Spacer ──
    lines.append(content_row(Text(""), w))

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
    lines.append(content_row(centered_hint, w))

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


# ── Input ────────────────────────────────────────────────────────────────


# ── Popup launcher ──────────────────────────────────────────────────────


def open_switcher_popup(backward: bool = False) -> None:
    """Calculate content size and spawn a fitted tmux popup."""
    registry = get_registry()
    registry.reload()

    current = get_current_tmux_session()
    statuses = get_all_session_statuses()
    projects = _get_active_projects(registry, statuses, current)

    if not projects:
        _display_message("kata: no active sessions")
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
    guard_tty()
    registry = get_registry()
    registry.reload()

    current = get_current_tmux_session()
    statuses = get_all_session_statuses()
    projects = _get_active_projects(registry, statuses, current)

    if not projects:
        print("kata: no active sessions", file=sys.stderr)
        return

    w, _ = _calc_popup_size(projects)
    selected = 0 if not backward else len(projects) - 1
    confirmed = False

    renderer = FrameRenderer(w)

    def _render_frame() -> str:
        return renderer.render(render_panel(projects, statuses, selected, current, w))

    with raw_screen() as fd:
        sys.stdout.write(_render_frame())
        sys.stdout.flush()

        while True:
            key = read_key(fd)

            if key in ("ctrl+space", "down", "tab"):
                selected = (selected + 1) % len(projects)
            elif key in ("up", "shift+tab"):
                selected = (selected - 1) % len(projects)
            elif key in ("enter", "space"):
                confirmed = True
                break
            elif key == "escape":
                break
            else:
                continue

            sys.stdout.write("\x1b[H")
            sys.stdout.write(_render_frame())
            sys.stdout.flush()

    if confirmed:
        _switch_to_session(projects[selected], registry)
