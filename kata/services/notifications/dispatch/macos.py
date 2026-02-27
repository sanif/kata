"""macOS native notification dispatcher (rewritten).

Sends notifications via terminal-notifier (preferred) or osascript (fallback).
Plays per-type sounds via afplay. Includes git branch in titles.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from kata.core.settings import get_settings
from kata.services.notifications.dispatch.audio import play_sound, resolve_sound_path
from kata.services.notifications.dispatch.summary import generate_summary
from kata.services.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)

# Emoji icons for macOS notification titles
TYPE_EMOJI: dict[NotificationType, str] = {
    NotificationType.TASK_COMPLETE: "✅",
    NotificationType.QUESTION: "❓",
    NotificationType.PLAN_READY: "📋",
    NotificationType.REVIEW_DONE: "🔍",
    NotificationType.ERROR: "🔴",
    NotificationType.SESSION_LIMIT: "⏱️",
    NotificationType.SESSION_LAUNCHED: "▸",
    NotificationType.SESSION_DETACHED: "◆",
    NotificationType.SESSION_ATTACHED: "▸",
    NotificationType.SESSION_KILLED: "✗",
    NotificationType.ROUTINE_COMPLETE: "◉",
}

# Default titles per notification type
TYPE_TITLES: dict[NotificationType, str] = {
    NotificationType.TASK_COMPLETE: "Task Completed",
    NotificationType.QUESTION: "Question Asked",
    NotificationType.PLAN_READY: "Plan Ready for Review",
    NotificationType.REVIEW_DONE: "Review Complete",
    NotificationType.ERROR: "Error Occurred",
    NotificationType.SESSION_LIMIT: "Session Limit Reached",
    NotificationType.SESSION_LAUNCHED: "Session Launched",
    NotificationType.SESSION_DETACHED: "Session Detached",
    NotificationType.SESSION_ATTACHED: "Session Attached",
    NotificationType.SESSION_KILLED: "Session Killed",
    NotificationType.ROUTINE_COMPLETE: "Routine Complete",
}


def get_git_branch(cwd: str) -> str:
    """Get current git branch name from a working directory."""
    if not cwd:
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def build_notification_title(
    notification_type: NotificationType,
    title: str,
    branch: str,
) -> str:
    """Build notification title with emoji and optional branch."""
    emoji = TYPE_EMOJI.get(notification_type, "•")
    parts = [f"{emoji} {title}"]
    if branch:
        parts.append(f"[{branch}]")
    return " ".join(parts)


def _has_terminal_notifier() -> bool:
    return shutil.which("terminal-notifier") is not None


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_macos_notification(notification: Notification) -> bool:
    """Send a native macOS notification with per-type sound.

    1. Build title with emoji + git branch
    2. Generate cleaned summary body
    3. Send OS notification (terminal-notifier or osascript) — no sound param
    4. Play type-specific sound via afplay
    """
    settings = get_settings()
    if not settings.notifications_os_enabled:
        return False

    # Build title with branch
    branch = notification.metadata.get("branch", "")
    if not branch:
        branch = get_git_branch(notification.metadata.get("cwd", ""))
    title = build_notification_title(notification.type, notification.title, branch)

    # Generate summary body
    body = generate_summary(notification.body) if notification.body else ""
    if notification.session_name and body:
        body = f"{notification.session_name} — {body}"
    elif notification.session_name:
        body = notification.session_name

    # Send OS notification (without sound — we handle sound separately)
    sent = False
    if _has_terminal_notifier():
        sent = _send_via_terminal_notifier(title, body, notification)
    else:
        sent = _send_via_osascript(title, body)

    # Play per-type sound
    if settings.notifications_sound_enabled:
        sound_path = resolve_sound_path(
            notification.type.value,
            settings.notifications_sounds,
            pack=settings.notifications_sound_pack,
        )
        if sound_path:
            play_sound(sound_path, settings.notifications_volume)

    return sent


def _send_via_terminal_notifier(title: str, body: str, notification: Notification) -> bool:
    cmd = [
        "terminal-notifier",
        "-title",
        title,
        "-message",
        body or " ",
        "-subtitle",
        notification.session_name or "",
        "-group",
        f"kata-{notification.type.value}",
        "-sender",
        "com.github.wez.wezterm",
    ]
    if notification.session_name:
        cmd.extend(["-execute", f"kata switch {notification.session_name}"])

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        logger.debug("terminal-notifier failed", exc_info=True)
        return False


def _send_via_osascript(title: str, body: str) -> bool:
    escaped_title = _escape_applescript(title)
    escaped_body = _escape_applescript(body or " ")
    script = f'display notification "{escaped_body}" ' f'with title "{escaped_title}"'
    try:
        subprocess.Popen(
            ["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        logger.debug("osascript notification failed", exc_info=True)
        return False
