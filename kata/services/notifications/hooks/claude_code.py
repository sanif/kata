"""Claude Code hook handler — rewritten with full dispatch pipeline.

Supports Stop, SubagentStop, PreToolUse, and Notification hook events.
Uses tool-based analyzer, two-phase dedup, per-type suppression, and summary generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from kata.core.settings import get_settings
from kata.services.notifications import notify
from kata.services.notifications.dispatch.analyzer import analyze_transcript
from kata.services.notifications.dispatch.dedup import acquire_lock, is_duplicate_early
from kata.services.notifications.dispatch.macos import TYPE_TITLES, get_git_branch
from kata.services.notifications.dispatch.state import (
    is_suppressed,
    load_session_state,
    update_session_state,
)
from kata.services.notifications.dispatch.summary import generate_summary
from kata.services.notifications.models import NotificationSource, NotificationType

logger = logging.getLogger(__name__)


def _resolve_session_name(cwd: str) -> str:
    """Resolve CWD to a Kata project/session name."""
    try:
        from kata.services.registry import get_registry

        registry = get_registry()
        project = registry.find_by_path(cwd)
        if project:
            return project.name
    except Exception:
        pass
    return Path(cwd).name if cwd else ""


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

    # 1. Dedup Phase 1 — early exit if recent lock
    if is_duplicate_early(session_id, event_type):
        return

    # 2. Classify
    if event_type == "pre-tool-use":
        tool_name = context.get("tool_name", "")
        if tool_name == "ExitPlanMode":
            notification_type = NotificationType.PLAN_READY
        elif tool_name == "AskUserQuestion":
            notification_type = NotificationType.QUESTION
        else:
            return  # Not a tool we care about
    elif event_type == "notification":
        notification_type = NotificationType.QUESTION
    else:
        # stop / subagent-stop — full transcript analysis
        notification_type = analyze_transcript(transcript_path, context)

    # 3. Dedup Phase 2 — atomic lock
    if not acquire_lock(session_id, event_type):
        return

    # 4. Suppression check
    state = load_session_state(session_id)
    if is_suppressed(
        notification_type,
        state,
        suppress_dup=settings.notifications_suppress_duplicate_seconds,
        suppress_q_task=settings.notifications_suppress_question_after_task_seconds,
        suppress_q_any=settings.notifications_suppress_question_after_any_seconds,
    ):
        return

    # 5. Build notification
    summary = generate_summary(last_message) if last_message else ""
    branch = get_git_branch(cwd)
    session_name = _resolve_session_name(cwd)
    title = TYPE_TITLES.get(notification_type, "Claude Code Event")

    # 6. Dispatch
    notify(
        type=notification_type,
        source=NotificationSource.CLAUDE_CODE,
        title=title,
        body=summary,
        session_name=session_name,
        metadata={
            "session_id": session_id,
            "cwd": cwd,
            "transcript_path": transcript_path,
            "branch": branch,
        },
    )

    # 7. Update session state
    update_session_state(session_id, notification_type)


def setup_hooks() -> None:
    """Set up Claude Code hooks in ~/.claude/settings.json.

    Registers hooks for: Stop, SubagentStop, PreToolUse, Notification.
    """
    settings_path = Path.home() / ".claude" / "settings.json"

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    hooks = existing.setdefault("hooks", {})

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
        already_exists = any(
            any(h.get("command", "").startswith("kata notify") for h in entry.get("hooks", []))
            for entry in event_hooks
        )
        if not already_exists:
            event_hooks.append(config)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
