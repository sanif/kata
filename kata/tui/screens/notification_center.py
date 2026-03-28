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
from kata.services.notifications.store import NotificationStore
from kata.utils.notifications import TYPE_ICONS, escape_rich, load_grouped, time_ago

# Short type labels for expanded view
TYPE_LABELS: dict[NotificationType, str] = {
    NotificationType.TASK_COMPLETE: "task",
    NotificationType.QUESTION: "question",
    NotificationType.PLAN_READY: "plan",
    NotificationType.REVIEW_DONE: "review",
    NotificationType.ERROR: "error",
    NotificationType.SESSION_LIMIT: "limit",
    NotificationType.ROUTINE_COMPLETE: "routine",
}

# Column widths
_COL_NAME = 18
_COL_COUNT = 8
_COL_TIME = 6
_COL_MSG = 36
_MAX_BODY_LINES = 12


def _get_message(n: Notification) -> str:
    """Get the display message — prefers body content over generic title."""
    body = getattr(n, "body", "") or ""
    if isinstance(body, str) and body.strip():
        first_line = body.strip().split("\n")[0].strip()
        if first_line:
            return first_line
    title = getattr(n, "title", "") or ""
    return title if isinstance(title, str) else str(title)


def _get_body_lines(n: Notification) -> list[str]:
    """Get all body lines for expanded view."""
    body = getattr(n, "body", "") or ""
    if not isinstance(body, str) or not body.strip():
        return []
    lines = body.strip().split("\n")
    # Skip the first line (already shown in summary) and collect the rest
    if len(lines) <= 1:
        return []
    remaining = [line.strip() for line in lines[1:] if line.strip()]
    return remaining[:_MAX_BODY_LINES]


class NotificationCenterModal(ModalScreen[str | None]):
    """Modal screen showing notifications grouped by project."""

    DEFAULT_CSS = """
    NotificationCenterModal {
        align: center middle;
        background: transparent;
    }

    NotificationCenterModal #nc-container {
        width: 78;
        max-width: 92%;
        height: 28;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    NotificationCenterModal #nc-header {
        width: 100%;
        height: 1;
        color: $text;
        background: transparent;
        padding: 0 1;
        margin-bottom: 1;
    }

    NotificationCenterModal #nc-tree {
        width: 100%;
        height: 1fr;
        background: transparent;
        scrollbar-size: 1 1;
        padding: 0;
    }

    NotificationCenterModal #nc-tree > .tree--cursor {
        background: $primary 15%;
    }

    NotificationCenterModal #nc-tree:focus > .tree--cursor {
        background: $primary 25%;
    }

    NotificationCenterModal #nc-tree > .tree--guides,
    NotificationCenterModal #nc-tree > .tree--guides-hover {
        color: $surface-lighten-1;
    }

    NotificationCenterModal #nc-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: transparent;
        margin-top: 1;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("v", "toggle_expand", "View", priority=True),
        Binding("d", "dismiss_selected", "Dismiss", priority=True),
        Binding("shift+d", "dismiss_all", "Dismiss All", priority=True),
        Binding("r", "mark_read", "Read", priority=True),
        Binding("shift+r", "mark_all_read", "Read All", priority=True),
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
        grouped = load_grouped()

        tree = self.query_one("#nc-tree", Tree)
        tree.clear()

        # Count total unread across all projects
        total_unread = 0
        total_count = 0
        for notifications in grouped.values():
            total_count += len(notifications)
            total_unread += sum(1 for n in notifications if n.status == NotificationStatus.UNREAD)

        # Header
        try:
            header = self.query_one("#nc-header", Static)
            if total_unread > 0:
                count_text = f"  [bold $primary]{total_unread} unread[/bold $primary]"
            elif total_count > 0:
                count_text = f"  [dim]{total_count} read[/dim]"
            else:
                count_text = ""
            header.update(f"[bold]󰂚 Notifications[/bold]{count_text}")
        except Exception:
            pass

        # Footer
        try:
            footer = self.query_one("#nc-footer", Static)
            footer.update(
                "[dim]enter[/dim] switch  "
                "[dim]v[/dim] expand  "
                "[dim]d[/dim] dismiss  [dim]D[/dim] all  "
                "[dim]r[/dim] read  [dim]R[/dim] all  "
                "[dim]esc[/dim] close"
            )
        except Exception:
            pass

        if not grouped:
            tree.root.add_leaf(
                "[dim]  No notifications yet[/dim]",
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
                body_lines = _get_body_lines(n)

                if body_lines:
                    # Expandable notification node with body lines as children
                    notif_node = project_node.add(
                        child_label,
                        data={
                            "type": "notification",
                            "notification_id": n.id,
                            "session_name": session_name,
                        },
                        expand=False,
                    )
                    for line in body_lines:
                        escaped_line = escape_rich(line)
                        if len(escaped_line) > 60:
                            escaped_line = escaped_line[:59] + "…"
                        notif_node.add_leaf(
                            f"[dim]  {escaped_line}[/dim]",
                            data={"type": "body_line", "session_name": session_name},
                        )
                else:
                    # Leaf notification (no body to expand)
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
        escaped_name = escape_rich(name)
        if len(escaped_name) > _COL_NAME:
            escaped_name = escaped_name[: _COL_NAME - 1] + "…"

        time_str = time_ago(most_recent)

        if unread > 0:
            count_str = f"{unread} new"
            return (
                f"[cyan]●[/cyan] "
                f"[bold]{escaped_name:<{_COL_NAME}}[/bold]  "
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
        type_label = TYPE_LABELS.get(n.type, "")
        message = escape_rich(_get_message(n)) or "Notification"

        # Shorter message to make room for type label
        max_msg = _COL_MSG - len(type_label) - 3 if type_label else _COL_MSG
        if len(message) > max_msg:
            message = message[: max_msg - 1] + "…"
        time_str = time_ago(n.timestamp)

        is_unread = n.status == NotificationStatus.UNREAD
        type_tag = f" [dim italic]{type_label}[/dim italic]" if type_label else ""

        if is_unread:
            return f"{icon} {message}{type_tag}" f"  [dim]{time_str:>{_COL_TIME}}[/dim]"
        else:
            return f"[dim]{icon} {message}{type_tag}  {time_str:>{_COL_TIME}}[/dim]"

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

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_toggle_expand(self) -> None:
        """Toggle expand/collapse on project or notification nodes."""
        try:
            tree = self.query_one("#nc-tree", Tree)
            node = tree.cursor_node
            if node is None or not node.data:
                return

            node_type = node.data.get("type")

            if node_type == "project":
                node.toggle()
            elif node_type == "notification":
                # Only toggle if the node has children (is expandable)
                if node.children:
                    node.toggle()
            elif node_type == "body_line":
                # Toggle the parent notification node
                if node.parent and node.parent.data:
                    node.parent.toggle()
        except Exception:
            pass

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle Enter on any node — switch to session."""
        data = event.node.data
        if not data or data.get("type") == "empty":
            return

        # For body lines, don't switch — just collapse parent
        if data.get("type") == "body_line":
            if event.node.parent and event.node.parent.data:
                event.node.parent.toggle()
            return

        session_name = data.get("session_name", "")
        if not session_name:
            self.app.notify("No session associated", severity="warning")
            return

        # Mark notifications read for this session
        try:
            with NotificationStore() as store:
                store.mark_session_read(session_name)
        except Exception:
            pass

        self.dismiss(session_name)

    def action_dismiss_selected(self) -> None:
        data = self._get_selected_data()
        if not data or data.get("type") == "empty":
            return

        try:
            with NotificationStore() as store:
                if data["type"] == "project":
                    store.dismiss_by_session(data["session_name"])
                elif data["type"] == "notification":
                    store.dismiss(data["notification_id"])
        except Exception:
            pass
        self._refresh_list()

    def action_dismiss_all(self) -> None:
        try:
            with NotificationStore() as store:
                store.dismiss_all()
        except Exception:
            pass
        self._refresh_list()

    def action_mark_read(self) -> None:
        data = self._get_selected_data()
        if not data or data.get("type") == "empty":
            return

        try:
            with NotificationStore() as store:
                if data["type"] == "project":
                    store.mark_session_read(data["session_name"])
                elif data["type"] == "notification":
                    store.update_status(data["notification_id"], NotificationStatus.READ)
        except Exception:
            pass
        self._refresh_list()

    def action_mark_all_read(self) -> None:
        try:
            with NotificationStore() as store:
                store.mark_all_read()
        except Exception:
            pass
        self._refresh_list()
