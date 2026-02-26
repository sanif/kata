"""Tmux hook handler for session events."""

from __future__ import annotations

import logging

from kata.services.notifications import notify
from kata.services.notifications.models import NotificationSource, NotificationType

logger = logging.getLogger(__name__)


def handle_tmux_event(event_type: str, session_name: str) -> None:
    """Handle a tmux hook event.

    Called by `kata notify-tmux-event <type> --session <name>`.
    """
    type_map = {
        "detached": NotificationType.SESSION_DETACHED,
        "attached": NotificationType.SESSION_ATTACHED,
    }

    notification_type = type_map.get(event_type)
    if not notification_type:
        logger.warning(f"Unknown tmux event type: {event_type}")
        return

    title_map = {
        "detached": f"Session detached: {session_name}",
        "attached": f"Session attached: {session_name}",
    }

    notify(
        type=notification_type,
        source=NotificationSource.TMUX,
        title=title_map.get(event_type, f"Tmux event: {event_type}"),
        session_name=session_name,
        priority=3,  # Low priority for attach/detach
    )


def register_tmux_hooks(session_name: str) -> None:
    """Register tmux hooks for a session to emit notifications."""
    import subprocess

    hooks = {
        "client-detached": f"kata notify-tmux-event detached --session {session_name}",
        "client-attached": f"kata notify-tmux-event attached --session {session_name}",
    }

    for hook_name, command in hooks.items():
        try:
            subprocess.run(
                [
                    "tmux",
                    "set-hook",
                    "-t",
                    session_name,
                    hook_name,
                    f"run-shell '{command}'",
                ],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            logger.debug(f"Failed to register tmux hook {hook_name}", exc_info=True)


def unregister_tmux_hooks(session_name: str) -> None:
    """Remove tmux hooks from a session."""
    import subprocess

    for hook_name in ("client-detached", "client-attached"):
        try:
            subprocess.run(
                ["tmux", "set-hook", "-u", "-t", session_name, hook_name],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
