"""Shared notification display utilities.

Extracted from notify_strip.py and notification_center.py to eliminate duplication.
"""

from __future__ import annotations

from datetime import datetime

from kata.services.notifications.models import Notification, NotificationType

# Compact icons per notification type
TYPE_ICONS: dict[NotificationType, str] = {
    NotificationType.TASK_COMPLETE: "󰄬",
    NotificationType.QUESTION: "?",
    NotificationType.PLAN_READY: "󰈙",
    NotificationType.REVIEW_DONE: "󰍉",
    NotificationType.ERROR: "✗",
    NotificationType.SESSION_LIMIT: "󰥔",
    NotificationType.ROUTINE_COMPLETE: "◉",
}


def time_ago(ts: datetime) -> str:
    """Format a timestamp as compact relative time (now, 5m, 2h, 3d)."""
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


def escape_rich(text: str) -> str:
    """Escape text for Rich markup (prevent bracket interpretation)."""
    if not text:
        return ""
    return text.replace("[", r"\[")


def load_grouped() -> dict[str, list[Notification]]:
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
