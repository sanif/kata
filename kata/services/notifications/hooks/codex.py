"""Codex CLI notify hook handler.

Codex uses a single `notify` command in ~/.codex/config.toml and passes
JSON payload when an agent turn completes.
"""

from __future__ import annotations

import json
import logging
import re
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
from kata.services.notifications.hooks.common import resolve_session_name
from kata.services.notifications.models import NotificationSource

logger = logging.getLogger(__name__)

_NOTIFY_LINE = 'notify = ["kata", "notify-hook", "codex"]'


def handle_hook_event(stdin_data: str) -> None:
    """Main entry point for Codex notify hook payload."""
    settings = get_settings()
    if not settings.notifications_enabled:
        return

    try:
        context = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError:
        logger.debug("Invalid JSON from Codex notify payload")
        return

    event_type = context.get("type", "agent-turn-complete")
    if not isinstance(event_type, str):
        event_type = "agent-turn-complete"

    session_id = (
        context.get("session_id")
        or context.get("thread_id")
        or context.get("conversation_id")
        or context.get("sessionId")
        or context.get("threadId")
        or context.get("conversationId")
        or "codex"
    )
    if not isinstance(session_id, str):
        session_id = "codex"

    transcript_path = str(context.get("transcript_path") or context.get("transcriptPath") or "")
    cwd = str(context.get("cwd") or context.get("workdir") or context.get("workspace_root") or "")
    last_message = str(
        context.get("last_assistant_message")
        or context.get("last-assistant-message")
        or context.get("assistant_message")
        or context.get("output_text")
        or ""
    )

    if is_duplicate_early(session_id, event_type):
        return

    notification_type = analyze_transcript(transcript_path, context)

    if not acquire_lock(session_id, event_type):
        return

    state = load_session_state(session_id)
    if is_suppressed(
        notification_type,
        state,
        suppress_dup=settings.notifications_suppress_duplicate_seconds,
        suppress_q_task=settings.notifications_suppress_question_after_task_seconds,
        suppress_q_any=settings.notifications_suppress_question_after_any_seconds,
    ):
        return

    summary = generate_summary(last_message) if last_message else ""
    branch = get_git_branch(cwd)
    session_name = resolve_session_name(cwd)
    title = TYPE_TITLES.get(notification_type, "Codex Event")

    notify(
        type=notification_type,
        source=NotificationSource.CODEX,
        title=title,
        body=summary,
        session_name=session_name,
        metadata={
            "event_type": event_type,
            "session_id": session_id,
            "cwd": cwd,
            "transcript_path": transcript_path,
            "branch": branch,
        },
    )

    update_session_state(session_id, notification_type)


def setup_hooks() -> None:
    """Set up Codex notify command in ~/.codex/config.toml."""
    config_path = Path.home() / ".codex" / "config.toml"
    text = config_path.read_text() if config_path.exists() else ""

    if "kata notify-hook codex" in text:
        return

    # Replace an existing top-level notify line/array if present.
    notify_re = re.compile(r"(?ms)^notify\s*=\s*\[(?:[^\]]|\n)*\]")
    if notify_re.search(text):
        text = notify_re.sub(_NOTIFY_LINE, text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += _NOTIFY_LINE + "\n"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text)
