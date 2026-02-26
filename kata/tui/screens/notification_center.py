"""Notification center modal screen."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from kata.services.notifications.models import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from kata.services.notifications.store import get_notification_store

TYPE_ICONS = {
    NotificationType.TASK_COMPLETE: "✅",
    NotificationType.QUESTION: "❓",
    NotificationType.PLAN_READY: "📋",
    NotificationType.REVIEW_DONE: "🔍",
    NotificationType.ERROR: "❌",
    NotificationType.SESSION_LIMIT: "⏱️",
    NotificationType.SESSION_LAUNCHED: "🚀",
    NotificationType.SESSION_DETACHED: "💤",
    NotificationType.SESSION_ATTACHED: "👋",
    NotificationType.SESSION_KILLED: "💀",
    NotificationType.ROUTINE_COMPLETE: "☀️",
}


def _time_ago(ts: datetime) -> str:
    """Format a timestamp as relative time."""
    delta = datetime.now() - ts
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


class NotificationCenterModal(ModalScreen[str | None]):
    """Modal screen showing all notifications with actions."""

    DEFAULT_CSS = """
    NotificationCenterModal {
        align: center middle;
    }

    NotificationCenterModal #notif-container {
        width: 90;
        height: 35;
        background: $surface;
        border: solid $surface-lighten-1;
        padding: 1 2;
    }

    NotificationCenterModal #notif-title {
        text-style: bold;
        color: $text;
        width: 100%;
        height: 1;
        margin-bottom: 1;
    }

    NotificationCenterModal #notif-list {
        width: 100%;
        height: 1fr;
        background: $surface;
    }

    NotificationCenterModal #notif-list > .option-list--option-highlighted {
        background: $primary 15%;
    }

    NotificationCenterModal #notif-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }

    NotificationCenterModal #notif-empty {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("d", "dismiss_selected", "Dismiss"),
        Binding("shift+d", "dismiss_all", "Dismiss All"),
        Binding("r", "mark_read", "Read"),
        Binding("shift+r", "mark_all_read", "Read All"),
    ]

    def __init__(self) -> None:
        """Initialize the notification center."""
        super().__init__()
        self._notifications: list[Notification] = []
        self._index_map: dict[int, int] = {}

    def compose(self) -> ComposeResult:
        """Compose the modal."""
        with Vertical(id="notif-container"):
            yield Static("", id="notif-title")
            yield OptionList(id="notif-list")
            yield Static(
                "[dim]Enter: Switch | d: Dismiss | D: Dismiss All | r: Read | R: Read All | Esc: Close[/dim]",
                id="notif-footer",
            )

    def on_mount(self) -> None:
        """Load notifications on mount."""
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the notification list from store."""
        store = get_notification_store()
        self._notifications = store.list_all(limit=50)
        self._index_map.clear()

        option_list = self.query_one("#notif-list", OptionList)
        option_list.clear_options()

        unread = sum(1 for n in self._notifications if n.status == NotificationStatus.UNREAD)
        title = self.query_one("#notif-title", Static)
        title.update(f"[bold]Notification Center[/bold]  ({unread} unread)")

        if not self._notifications:
            option_list.add_option(Option("[dim]No notifications[/dim]", disabled=True))
            return

        for i, n in enumerate(self._notifications):
            icon = TYPE_ICONS.get(n.type, "🔔")
            time_str = _time_ago(n.timestamp)
            status_badge = (
                "[bold red]● NEW[/bold red]"
                if n.status == NotificationStatus.UNREAD
                else "[dim]○[/dim]"
            )
            session = f"[cyan]{n.session_name}[/cyan]" if n.session_name else ""
            # First line: icon, title, session, status
            line1 = f" {icon} {n.title:<34} {session:<16} {status_badge}"
            # Second line: time and body preview
            body_preview = ""
            if n.body:
                first_line = n.body.strip().split("\n")[0][:50]
                body_preview = f" · {first_line}"
            line2 = f"    [dim]{time_str}{body_preview}[/dim]"
            label = f"{line1}\n{line2}"
            option_list.add_option(Option(label))
            self._index_map[i] = i

    def _get_selected_notification(self) -> Notification | None:
        """Get the currently highlighted notification."""
        option_list = self.query_one("#notif-list", OptionList)
        idx = option_list.highlighted
        if idx is not None and idx in self._index_map:
            return self._notifications[self._index_map[idx]]
        return None

    def action_cancel(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle Enter key on an option (switch to session)."""
        n = self._get_selected_notification()
        if not n:
            return

        # Mark as read
        store = get_notification_store()
        store.update_status(n.id, NotificationStatus.READ)

        if n.session_name:
            self.dismiss(n.session_name)
        else:
            self.app.notify("No session associated with this notification", severity="warning")

    def action_dismiss_selected(self) -> None:
        """Dismiss the selected notification."""
        n = self._get_selected_notification()
        if not n:
            return
        store = get_notification_store()
        store.dismiss(n.id)
        self._refresh_list()

    def action_dismiss_all(self) -> None:
        """Dismiss all notifications."""
        store = get_notification_store()
        store.dismiss_all()
        self._refresh_list()

    def action_mark_read(self) -> None:
        """Mark the selected notification as read."""
        n = self._get_selected_notification()
        if not n:
            return
        store = get_notification_store()
        store.update_status(n.id, NotificationStatus.READ)
        self._refresh_list()

    def action_mark_all_read(self) -> None:
        """Mark all notifications as read."""
        store = get_notification_store()
        store.mark_all_read()
        self._refresh_list()
