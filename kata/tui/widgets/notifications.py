"""Notification badge widget for the TUI header."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget


class NotificationBadge(Widget):
    """Badge showing unread notification count."""

    DEFAULT_CSS = """
    NotificationBadge {
        width: auto;
        height: 1;
        margin: 0 1;
    }
    """

    unread_count: reactive[int] = reactive(0)

    def __init__(
        self,
        unread_count: int = 0,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the badge."""
        super().__init__(name=name, id=id, classes=classes)
        self.unread_count = unread_count

    def render(self) -> str:
        """Render the badge text."""
        if self.unread_count > 0:
            return f"[bold on red] 🔔 {self.unread_count} [/]"
        return "[dim]🔔 0[/dim]"

    def watch_unread_count(self) -> None:
        """React to count changes."""
        self.refresh()

    def update_count(self, count: int) -> None:
        """Update the badge count."""
        self.unread_count = count
