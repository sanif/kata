"""Pure rendering utilities for the project switcher strip.

Shared by both the TUI modal (Textual) and CLI strip (Rich).
No framework-specific dependencies.
"""

from __future__ import annotations

from kata.core.models import Project, SessionStatus
from kata.utils.paths import sanitize_session_name


def get_status_indicator(status: SessionStatus) -> str:
    """Return Rich-formatted status dot."""
    return {
        SessionStatus.ACTIVE: "[green]●[/green]",
        SessionStatus.DETACHED: "[yellow]●[/yellow]",
        SessionStatus.IDLE: "[dim]○[/dim]",
    }[status]


def cycle_index(current: int, total: int) -> int:
    """Advance index by 1 with wraparound."""
    return (current + 1) % total


def render_switcher_strip(
    projects: list[Project],
    statuses: dict[str, SessionStatus],
    selected_index: int,
    current_session: str | None = None,
) -> str:
    """Render the horizontal strip as a Rich markup string."""
    parts = []
    for i, project in enumerate(projects):
        sname = sanitize_session_name(project.name)
        status = statuses.get(sname, SessionStatus.IDLE)
        dot = get_status_indicator(status)

        if i == selected_index:
            parts.append(f"[bold reverse] {dot} {project.name} [/bold reverse]")
        elif current_session and (project.name == current_session or sname == current_session):
            parts.append(f"[dim]{dot} {project.name}[/dim]")
        else:
            parts.append(f"{dot} {project.name}")
    return "    ".join(parts)
