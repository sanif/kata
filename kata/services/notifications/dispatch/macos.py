"""macOS native notification dispatcher."""

from __future__ import annotations

import logging
import shutil
import subprocess

from kata.core.settings import get_settings
from kata.services.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)

# Icons by notification type
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


def _has_terminal_notifier() -> bool:
    """Check if terminal-notifier is installed."""
    return shutil.which("terminal-notifier") is not None


def _escape_applescript(text: str) -> str:
    """Escape text for use in AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_macos_notification(notification: Notification) -> bool:
    """Send a native macOS notification.

    Uses terminal-notifier if available (supports click callbacks),
    falls back to osascript.

    Returns True if notification was sent successfully.
    """
    settings = get_settings()
    if not settings.notifications_os_enabled:
        return False

    icon = TYPE_ICONS.get(notification.type, "🔔")
    title = f"{icon} {notification.title}"
    body = notification.body or notification.session_name
    sound = settings.notifications_sound

    if _has_terminal_notifier():
        return _send_via_terminal_notifier(title, body, sound, notification)
    else:
        return _send_via_osascript(title, body, sound)


def _send_via_terminal_notifier(
    title: str,
    body: str,
    sound: str,
    notification: Notification,
) -> bool:
    """Send notification via terminal-notifier (supports click-to-focus)."""
    cmd = [
        "terminal-notifier",
        "-title",
        title,
        "-message",
        body or " ",
        "-sound",
        sound,
        "-group",
        f"kata-{notification.id}",
    ]

    # Add click-to-switch callback if session is known
    if notification.session_name:
        cmd.extend(["-execute", f"kata switch {notification.session_name}"])

    try:
        subprocess.run(cmd, capture_output=True, timeout=5)
        return True
    except Exception:
        logger.debug("terminal-notifier failed", exc_info=True)
        return False


def _send_via_osascript(title: str, body: str, sound: str) -> bool:
    """Send notification via osascript (built-in, no click support)."""
    escaped_title = _escape_applescript(title)
    escaped_body = _escape_applescript(body or " ")
    script = (
        f'display notification "{escaped_body}" with title "{escaped_title}" sound name "{sound}"'
    )

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        logger.debug("osascript notification failed", exc_info=True)
        return False
