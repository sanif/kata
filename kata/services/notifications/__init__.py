"""Notification system for Kata.

Public API:
    notify()                    — Send a notification (sync, fire-and-forget)
    NotificationClient          — Async client for daemon communication
    get_notification_store()    — Direct SQLite store access
"""

from __future__ import annotations

import logging
from typing import Any

from kata.services.notifications.client import NotificationClient, send_notification_sync
from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationStatus,
    NotificationType,
)
from kata.services.notifications.store import NotificationStore, get_notification_store

logger = logging.getLogger(__name__)

__all__ = [
    "notify",
    "Notification",
    "NotificationClient",
    "NotificationSource",
    "NotificationStatus",
    "NotificationType",
    "NotificationStore",
    "get_notification_store",
]


def notify(
    type: NotificationType,
    source: NotificationSource,
    title: str,
    body: str = "",
    session_name: str = "",
    priority: int = 2,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Send a notification (fire-and-forget).

    Tries to send via daemon socket. If daemon is not running,
    writes directly to SQLite store as fallback.

    This is the primary API for Kata services to emit notifications.
    """
    from kata.core.settings import get_settings

    settings = get_settings()
    if not settings.notifications_enabled:
        return

    # Per-project disable check
    if session_name and session_name in settings.notifications_disabled_projects:
        return

    notification = Notification(
        type=type,
        source=source,
        title=title,
        body=body,
        session_name=session_name,
        priority=priority,
        metadata=metadata or {},
    )

    # Try daemon first
    sent = send_notification_sync(notification)
    if not sent:
        # Fallback: write directly to store with a fresh connection
        # to avoid locking issues with long-lived processes (e.g., TUI)
        try:
            store = NotificationStore()
            try:
                store.add(notification)
            finally:
                store.close()
        except Exception:
            logger.debug("Failed to store notification", exc_info=True)

    # Dispatch OS-level notification (non-blocking, best-effort)
    try:
        import platform

        if platform.system() == "Darwin":
            from kata.services.notifications.dispatch.macos import send_macos_notification

            send_macos_notification(notification)
    except Exception:
        logger.debug("Failed to send OS notification", exc_info=True)
