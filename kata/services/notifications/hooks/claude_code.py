"""Claude Code hook handler — rewritten with full dispatch pipeline.

Supports Stop, SubagentStop, PreToolUse, and Notification hook events.
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
    """Main entry point for Claude Code hook events.

    Args:
        event_type: "stop", "subagent-stop", "pre-tool-use", or "notification"
        stdin_data: JSON string from Claude Code hook stdin
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
    last_message = context.get("last_assistant_message", "")

    # Skip subagent events if disabled
    if event_type == "subagent-stop" and not settings.notifications_subagent_stop:
        return

    # Classify (deferred into a callable so transcript analysis is skipped for
    # deduplicated events).
    if event_type == "pre-tool-use":
        tool_name = context.get("tool_name", "")
        if tool_name == "ExitPlanMode":
            notification_type = NotificationType.PLAN_READY
        elif tool_name == "AskUserQuestion":
            notification_type = NotificationType.QUESTION
        else:
            return  # Not a tool we care about

        def classify() -> NotificationType:
            return notification_type
    elif event_type == "notification":
        # Permission-request / question payloads carry the human-readable prompt
        # in ``message``; use it as the body so it isn't an empty banner.
        last_message = str(context.get("message", "") or last_message)

        def classify() -> NotificationType:
            return NotificationType.QUESTION
    else:
        # stop / subagent-stop — full transcript analysis
        def classify() -> NotificationType:
            return analyze_transcript(transcript_path, context)

    run_hook_pipeline(
        source=NotificationSource.CLAUDE_CODE,
        event_type=event_type,
        session_id=session_id,
        classify=classify,
        settings=settings,
        cwd=cwd,
        transcript_path=transcript_path,
        last_message=last_message,
        default_title="Claude Code Event",
    )


def setup_hooks() -> None:
    """Set up Claude Code hooks in ~/.claude/settings.json.

    Registers hooks for: Stop, SubagentStop, PreToolUse, Notification.
    """
    settings_path = Path.home() / ".claude" / "settings.json"

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        existing = {}

    if not isinstance(existing, dict):
        existing = {}

    hooks = existing.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        existing["hooks"] = hooks

    # Define hook configurations
    hook_configs = {
        "Stop": {
            "matcher": "",
            "hooks": [{"type": "command", "command": "kata notify-hook stop"}],
        },
        "SubagentStop": {
            "matcher": "",
            "hooks": [{"type": "command", "command": "kata notify-hook subagent-stop"}],
        },
        "PreToolUse": {
            "matcher": "ExitPlanMode|AskUserQuestion",
            "hooks": [{"type": "command", "command": "kata notify-hook pre-tool-use"}],
        },
        "Notification": {
            "matcher": ".",
            "hooks": [{"type": "command", "command": "kata notify-hook notification"}],
        },
    }

    for event, config in hook_configs.items():
        event_hooks = hooks.setdefault(event, [])
        if not isinstance(event_hooks, list):
            event_hooks = []
            hooks[event] = event_hooks
        already_exists = any(
            isinstance(entry, dict)
            and any(
                isinstance(h, dict) and h.get("command", "").startswith("kata notify")
                for h in entry.get("hooks", [])
            )
            for entry in event_hooks
        )
        if not already_exists:
            event_hooks.append(config)

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    except OSError as e:
        logger.error(f"Failed to setup Claude Code hooks: {e}")
