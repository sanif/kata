"""Notification center modal screen — project-centric tree view."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Tree

from kata.services.notifications.models import (
    Notification,
    NotificationStatus,
    NotificationType,
)

# Compact icons per notification type
TYPE_ICONS: dict[NotificationType, str] = {
    NotificationType.TASK_COMPLETE: "󰄬",
    NotificationType.QUESTION: "?",
    NotificationType.PLAN_READY: "󰈙",
    NotificationType.REVIEW_DONE: "󰍉",
    NotificationType.ERROR: "✗",
    NotificationType.SESSION_LIMIT: "󰥔",
    NotificationType.SESSION_LAUNCHED: "▸",
    NotificationType.SESSION_DETACHED: "◆",
    NotificationType.SESSION_ATTACHED: "▸",
    NotificationType.SESSION_KILLED: "✗",
    NotificationType.ROUTINE_COMPLETE: "◉",
}

# Column widths
_COL_NAME = 18
_COL_COUNT = 8
_COL_TIME = 6
_COL_MSG = 36


def _time_ago(ts: datetime) -> str:
    """Format a timestamp as compact relative time."""
    try:
        delta = datetime.now() - ts
        seconds = int(delta.total_seconds())
        if seconds < 0:
            return ""
        if seconds < 60:
            return "now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"
    except Exception:
        return ""


def _escape(text: str) -> str:
    """Escape text for Rich markup."""
    if not text or not isinstance(text, str):
        return ""
    return text.replace("[", r"\[")


def _get_message(n: Notification) -> str:
    """Get the display message — prefers body content over generic title."""
    body = getattr(n, "body", "") or ""
    if isinstance(body, str) and body.strip():
        first_line = body.strip().split("\n")[0].strip()
        if first_line:
            return first_line
    title = getattr(n, "title", "") or ""
    return title if isinstance(title, str) else str(title)


def _load_grouped() -> dict[str, list[Notification]]:
    """Load notifications grouped by session using a fresh DB connection."""
    try:
        from kata.services.notifications.store import NotificationStore

        store = NotificationStore()
        try:
            return store.list_grouped_by_session()
        finally:
            store.close()
    except Exception:
        return {}


class NotificationCenterModal(ModalScreen[str | None]):
    """Modal screen showing notifications grouped by project."""

    DEFAULT_CSS = """
    NotificationCenterModal {
        align: center middle;
        background: transparent;
    }

    NotificationCenterModal #nc-container {
        width: 74;
        max-width: 90%;
        height: 24;
        background: transparent;
        border: round $primary 40%;
        padding: 1 1;
    }

    NotificationCenterModal #nc-header {
        width: 100%;
        height: 1;
        color: $text;
        background: transparent;
        padding: 0 1;
    }

    NotificationCenterModal #nc-tree {
        width: 100%;
        height: 1fr;
        background: transparent;
        scrollbar-size: 1 1;
        padding: 0;
    }

    NotificationCenterModal #nc-tree > .tree--cursor {
        background: $surface-lighten-2;
    }

    NotificationCenterModal #nc-tree:focus > .tree--cursor {
        background: $primary 25%;
    }

    NotificationCenterModal #nc-tree > .tree--guides,
    NotificationCenterModal #nc-tree > .tree--guides-hover {
        color: transparent;
    }

    NotificationCenterModal #nc-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: transparent;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("v", "toggle_expand", "View"),
        Binding("d", "dismiss_selected", "Dismiss"),
        Binding("shift+d", "dismiss_all", "Dismiss All"),
        Binding("r", "mark_read", "Read"),
        Binding("shift+r", "mark_all_read", "Read All"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="nc-container"):
            yield Static("", id="nc-header")
            yield Tree("", id="nc-tree")
            yield Static("", id="nc-footer")

    def on_mount(self) -> None:
        tree = self.query_one("#nc-tree", Tree)
        tree.show_root = False
        tree.guide_depth = 2
        self._refresh_list()
        tree.focus()

    def _refresh_list(self) -> None:
        """Reload notifications and rebuild the tree."""
        grouped = _load_grouped()

        tree = self.query_one("#nc-tree", Tree)
        tree.clear()

        # Count total unread across all projects
        total_unread = 0
        for notifications in grouped.values():
            total_unread += sum(1 for n in notifications if n.status == NotificationStatus.UNREAD)

        # Header
        try:
            header = self.query_one("#nc-header", Static)
            count_text = f"  [cyan]{len(grouped)}[/cyan]" if grouped else ""
            header.update(f"[bold]󰂚 Notifications[/bold]{count_text}")
        except Exception:
            pass

        # Footer
        try:
            footer = self.query_one("#nc-footer", Static)
            footer.update(
                "[dim]enter[/dim] switch  "
                "[dim]v[/dim] view  "
                "[dim]d[/dim] dismiss  [dim]D[/dim] all  "
                "[dim]r[/dim] read  [dim]R[/dim] all  "
                "[dim]esc[/dim] close"
            )
        except Exception:
            pass

        if not grouped:
            tree.root.add_leaf(
                "[dim]  No notifications[/dim]",
                data={"type": "empty"},
            )
            return

        for session_name, notifications in grouped.items():
            unread = sum(1 for n in notifications if n.status == NotificationStatus.UNREAD)
            most_recent = notifications[0].timestamp  # Already sorted DESC
            label = self._build_project_label(session_name, unread, most_recent)

            project_node = tree.root.add(
                label,
                data={"type": "project", "session_name": session_name},
                expand=False,
            )

            for n in notifications:
                child_label = self._build_notification_label(n)
                project_node.add_leaf(
                    child_label,
                    data={
                        "type": "notification",
                        "notification_id": n.id,
                        "session_name": session_name,
                    },
                )

    def _build_project_label(self, name: str, unread: int, most_recent: datetime) -> str:
        """Build label for a project row."""
        escaped_name = _escape(name)
        if len(escaped_name) > _COL_NAME:
            escaped_name = escaped_name[: _COL_NAME - 1] + "…"

        time_str = _time_ago(most_recent)

        if unread > 0:
            count_str = f"{unread} new"
            return (
                f"[cyan]●[/cyan] "
                f"{escaped_name:<{_COL_NAME}}  "
                f"[cyan]{count_str:<{_COL_COUNT}}[/cyan] "
                f"[dim]{time_str:>{_COL_TIME}}[/dim]"
            )
        else:
            return (
                f"[dim]○ "
                f"{escaped_name:<{_COL_NAME}}  "
                f"{'—':<{_COL_COUNT}} "
                f"{time_str:>{_COL_TIME}}[/dim]"
            )

    def _build_notification_label(self, n: Notification) -> str:
        """Build label for a notification child row."""
        icon = TYPE_ICONS.get(n.type, "•")
        message = _escape(_get_message(n)) or "Notification"
        if len(message) > _COL_MSG:
            message = message[: _COL_MSG - 1] + "…"
        time_str = _time_ago(n.timestamp)

        is_unread = n.status == NotificationStatus.UNREAD
        if is_unread:
            return f"{icon} {message:<{_COL_MSG}} [dim]{time_str:>{_COL_TIME}}[/dim]"
        else:
            return f"[dim]{icon} {message:<{_COL_MSG}} {time_str:>{_COL_TIME}}[/dim]"

    def _get_selected_data(self) -> dict[str, Any] | None:
        """Get data from the currently highlighted tree node."""
        try:
            tree = self.query_one("#nc-tree", Tree)
            node = tree.cursor_node
            if node is not None and node.data:
                return node.data
        except Exception:
            pass
        return None

    def _get_store(self):
        from kata.services.notifications.store import NotificationStore

        return NotificationStore()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_toggle_expand(self) -> None:
        """Toggle expand/collapse on project nodes."""
        try:
            tree = self.query_one("#nc-tree", Tree)
            node = tree.cursor_node
            if node is None or not node.data:
                return
            if node.data.get("type") == "project":
                node.toggle()
        except Exception:
            pass

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle Enter on any node — switch to session."""
        data = event.node.data
        if not data or data.get("type") == "empty":
            return

        session_name = data.get("session_name", "")
        if not session_name:
            self.app.notify("No session associated", severity="warning")
            return

        # Mark notifications read for this session
        try:
            store = self._get_store()
            try:
                store.mark_session_read(session_name)
            finally:
                store.close()
        except Exception:
            pass

        self.dismiss(session_name)

    def action_dismiss_selected(self) -> None:
        data = self._get_selected_data()
        if not data or data.get("type") == "empty":
            return

        try:
            store = self._get_store()
            try:
                if data["type"] == "project":
                    store.dismiss_by_session(data["session_name"])
                elif data["type"] == "notification":
                    store.dismiss(data["notification_id"])
            finally:
                store.close()
        except Exception:
            pass
        self._refresh_list()

    def action_dismiss_all(self) -> None:
        try:
            store = self._get_store()
            try:
                store.dismiss_all()
            finally:
                store.close()
        except Exception:
            pass
        self._refresh_list()

    def action_mark_read(self) -> None:
        data = self._get_selected_data()
        if not data or data.get("type") == "empty":
            return

        try:
            store = self._get_store()
            try:
                if data["type"] == "project":
                    store.mark_session_read(data["session_name"])
                elif data["type"] == "notification":
                    store.update_status(data["notification_id"], NotificationStatus.READ)
            finally:
                store.close()
        except Exception:
            pass
        self._refresh_list()

    def action_mark_all_read(self) -> None:
        try:
            store = self._get_store()
            try:
                store.mark_all_read()
            finally:
                store.close()
        except Exception:
            pass
        self._refresh_list()
