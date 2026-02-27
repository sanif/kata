"""Gemini CLI hook handler — rewritten with full dispatch pipeline.

Supports AfterAgent, BeforeTool, Notification, and SessionEnd hook events.
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

    # 1. Dedup Phase 1 — early exit if recent lock
    if is_duplicate_early(session_id, event_type):
        return

    # 2. Classify
    if event_type == "before-tool":
        tool_name = context.get("tool_name", "")
        # Map Gemini tool names
        if tool_name == "ask_user":
            notification_type = NotificationType.QUESTION
        else:
            return  # Not a tool we care about for pre-tool notifications
    elif event_type == "notification":
        # System-level notifications from Gemini CLI
        notification_type = NotificationType.QUESTION
    else:
        # after-agent / session-end — full transcript analysis
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
    title = TYPE_TITLES.get(notification_type, "Gemini CLI Event")

    # 6. Dispatch
    notify(
        type=notification_type,
        source=NotificationSource.GEMINI,
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
