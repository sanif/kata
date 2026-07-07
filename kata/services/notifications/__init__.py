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

# Prune at most once per process on the direct-SQLite fallback path, so that
# retention settings still take effect for hook-only users who never run the TUI
# or daemon (each hook invocation is a fresh, short-lived process).
_pruned_this_process = False

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
        stored = False
        try:
            store = NotificationStore()
            try:
                store.add(notification)
                stored = True
                _prune_fallback_once(store, settings)
            finally:
                store.close()
        except Exception:
            logger.debug("Failed to store notification", exc_info=True)

        if not stored:
            # BOTH the daemon send and the store write failed: this notification
            # is fully lost. Record one diagnostic line so total loss isn't
            # completely silent (everything else stays at debug level).
            _log_notification_loss(notification)

    # Dispatch OS-level notification (non-blocking, best-effort)
    try:
        import platform

        if platform.system() == "Darwin":
            from kata.services.notifications.dispatch.macos import send_macos_notification

            send_macos_notification(notification)
    except Exception:
        logger.debug("Failed to send OS notification", exc_info=True)


def _prune_fallback_once(store: NotificationStore, settings: Any) -> None:
    """Prune the store once per process on the direct-SQLite fallback path."""
    global _pruned_this_process
    if _pruned_this_process:
        return
    _pruned_this_process = True
    try:
        store.prune(
            max_age_days=settings.notifications_retention_days,
            max_count=settings.notifications_max_count,
        )
    except Exception:
        logger.debug("Fallback prune failed", exc_info=True)


def _log_notification_loss(notification: Notification) -> None:
    """Best-effort single-line record of a fully-lost notification."""
    try:
        from datetime import datetime

        from kata.core.config import KATA_CONFIG_DIR, ensure_config_dirs

        ensure_config_dirs()
        log_path = KATA_CONFIG_DIR / "notifications-error.log"
        line = (
            f"{datetime.now().isoformat()} LOST "
            f"{notification.source.value}/{notification.type.value} "
            f"session={notification.session_name!r} title={notification.title!r} "
            "(daemon send AND store write both failed)\n"
        )
        with open(log_path, "a") as f:
            f.write(line)
    except Exception:
        logger.debug("Failed to write notification-loss log", exc_info=True)
