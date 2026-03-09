"""Quick project switcher modal — Cmd+Tab-style horizontal strip."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from kata.core.models import Project, SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import (
    get_all_session_statuses,
    get_current_tmux_session,
)
from kata.utils.switcher import cycle_index, render_switcher_strip


class SwitcherModal(ModalScreen[Project | None]):
    """Cmd+Tab-style project switcher strip."""

    DEFAULT_CSS = """
    SwitcherModal {
        align: center middle;
    }

    SwitcherModal #switcher-container {
        width: auto;
        max-width: 90;
        height: auto;
        max-height: 5;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
        content-align: center middle;
    }

    SwitcherModal #switcher-strip {
        width: auto;
        height: 1;
        content-align: center middle;
        text-align: center;
    }

    SwitcherModal #switcher-hint {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("space", "cycle", "Next", show=False),
        Binding("enter", "confirm", "Switch", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._projects: list[Project] = []
        self._statuses: dict[str, SessionStatus] = {}
        self._selected_index: int = 0
        self._current_session: str | None = None

    def compose(self):
        with Vertical(id="switcher-container"):
            yield Static("", id="switcher-strip")
            yield Static(
                "[dim]Space[/dim] cycle  [dim]Enter[/dim] switch  [dim]Esc[/dim] cancel",
                id="switcher-hint",
            )

    def on_mount(self) -> None:
        registry = get_registry()
        registry.reload()
        self._current_session = get_current_tmux_session()
        self._projects = registry.get_recent_projects(
            limit=5, current_session=self._current_session
        )
        self._statuses = get_all_session_statuses()
        self._selected_index = 0
        self._update_strip()

    def _update_strip(self) -> None:
        if not self._projects:
            self.query_one("#switcher-strip", Static).update("[dim]No projects[/dim]")
            return
        markup = render_switcher_strip(
            self._projects,
            self._statuses,
            self._selected_index,
            self._current_session,
        )
        self.query_one("#switcher-strip", Static).update(markup)

    def action_cycle(self) -> None:
        if self._projects:
            self._selected_index = cycle_index(self._selected_index, len(self._projects))
            self._update_strip()

    def action_confirm(self) -> None:
        if self._projects:
            self.dismiss(self._projects[self._selected_index])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
