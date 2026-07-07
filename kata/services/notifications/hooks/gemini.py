"""Gemini CLI hook handler — rewritten with full dispatch pipeline.

Supports AfterAgent, BeforeTool, Notification, and SessionEnd hook events.
Uses tool-based analyzer, two-phase dedup, per-type suppression, and summary generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from kata.core.settings import get_settings
from kata.services.notifications.dispatch.analyzer import analyze_transcript
from kata.services.notifications.hooks.common import run_hook_pipeline
from kata.services.notifications.models import NotificationSource, NotificationType

logger = logging.getLogger(__name__)


def handle_hook_event(event_type: str, stdin_data: str) -> None:
    """Main entry point for Gemini CLI hook events.

    Args:
        event_type: "after-agent", "before-tool", "notification", or "session-end"
        stdin_data: JSON string from Gemini CLI hook stdin
    """
    settings = get_settings()
    if not settings.notifications_enabled:
        return

    # Parse stdin
    try:
        context = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError:
        logger.debug("Invalid JSON from hook stdin")
        return

    session_id = context.get("session_id", "")
    if not session_id:
        logger.debug("No session_id in hook context, skipping")
        return

    transcript_path = context.get("transcript_path", "")
    cwd = context.get("cwd", "")
    last_message = context.get("prompt_response", "")

    # Classify (deferred so transcript analysis is skipped for dedup'd events).
    if event_type == "before-tool":
        tool_name = context.get("tool_name", "")
        # Map Gemini tool names
        if tool_name == "ask_user":
            notification_type = NotificationType.QUESTION
        else:
            return  # Not a tool we care about for pre-tool notifications

        def classify() -> NotificationType:
            return notification_type
    elif event_type == "notification":
        # System-level notifications from Gemini CLI
        last_message = str(context.get("message", "") or last_message)

        def classify() -> NotificationType:
            return NotificationType.QUESTION
    else:
        # after-agent / session-end — full transcript analysis
        def classify() -> NotificationType:
            return analyze_transcript(transcript_path, context)

    run_hook_pipeline(
        source=NotificationSource.GEMINI,
        event_type=event_type,
        session_id=session_id,
        classify=classify,
        settings=settings,
        cwd=cwd,
        transcript_path=transcript_path,
        last_message=last_message,
        default_title="Gemini CLI Event",
    )


def setup_hooks() -> None:
    """Set up Gemini CLI hooks in ~/.gemini/settings.json.

    Registers hooks for: AfterAgent, BeforeTool, Notification, SessionEnd.
    """
    settings_path = Path.home() / ".gemini" / "settings.json"

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    hooks = existing.setdefault("hooks", {})

    # Define hook configurations
    # Gemini uses PascalCase for hook events in settings.json
    hook_configs = {
        "AfterAgent": {
            "matcher": "",
            "hooks": [{"type": "command", "command": "kata notify-hook after-agent"}],
        },
        "BeforeTool": {
            "matcher": "ask_user",
            "hooks": [{"type": "command", "command": "kata notify-hook before-tool"}],
        },
        "Notification": {
            "matcher": ".",
            "hooks": [{"type": "command", "command": "kata notify-hook notification"}],
        },
        "SessionEnd": {
            "matcher": "",
            "hooks": [{"type": "command", "command": "kata notify-hook session-end"}],
        },
    }

    for event, config in hook_configs.items():
        event_hooks = hooks.setdefault(event, [])
        already_exists = any(
            any(h.get("command", "").startswith("kata notify") for h in entry.get("hooks", []))
            for entry in event_hooks
        )
        if not already_exists:
            event_hooks.append(config)

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    except Exception as e:
        logger.error(f"Failed to setup Gemini hooks: {e}")
