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
from kata.services.notifications.hooks.common import run_hook_pipeline
from kata.services.notifications.models import NotificationSource, NotificationType

logger = logging.getLogger(__name__)

_NOTIFY_LINE = 'notify = ["kata", "notify-hook", "codex"]'
# Matches kata's own top-level notify assignment (single-line array form we write).
_KATA_NOTIFY_RE = re.compile(
    r'notify\s*=\s*\[\s*"kata"\s*,\s*"notify-hook"\s*,\s*"codex"\s*,?\s*\]'
)


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

    # Codex only fires on agent-turn-complete and never provides a transcript we
    # can classify from, so the type is always TASK_COMPLETE — classify directly
    # instead of running the (no-op) transcript analyzer.
    def classify() -> NotificationType:
        return NotificationType.TASK_COMPLETE

    run_hook_pipeline(
        source=NotificationSource.CODEX,
        event_type=event_type,
        session_id=session_id,
        classify=classify,
        settings=settings,
        cwd=cwd,
        transcript_path=transcript_path,
        last_message=last_message,
        extra_metadata={"event_type": event_type},
        default_title="Codex Event",
    )


def setup_hooks() -> str:
    """Set up Codex notify command in ~/.codex/config.toml.

    Codex reads a *top-level* ``notify`` key, so the assignment must appear
    before any ``[table]`` header. Behavior:

    * If kata's notify is already installed at top level -> ``"already_installed"``.
    * If a *different* top-level ``notify`` command already exists, it is
      preserved (never clobbered) and kata is NOT installed ->
      ``"existing_notify_preserved"`` (the setup UI should surface this so the
      user can merge manually).
    * Otherwise kata's notify line is prepended at the very top of the file ->
      ``"installed"``.
    """
    config_path = Path.home() / ".codex" / "config.toml"
    text = config_path.read_text() if config_path.exists() else ""

    lines = text.splitlines()

    # The top-level region ends at the first table header (``[...]``).
    top_end = len(lines)
    for i, line in enumerate(lines):
        if re.match(r"\s*\[", line):
            top_end = i
            break
    top_text = "\n".join(lines[:top_end])

    # Already correctly installed at top level?
    if _KATA_NOTIFY_RE.search(top_text):
        return "already_installed"

    # A different top-level notify assignment? Preserve it, do not clobber.
    for i in range(top_end):
        if re.match(r"\s*notify\s*=", lines[i]):
            logger.debug("Codex config has a user-owned top-level notify; preserving it")
            return "existing_notify_preserved"

    # Prepend kata's notify at the very top (before any table header).
    new_text = _NOTIFY_LINE + "\n" + text if text else _NOTIFY_LINE + "\n"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(new_text)
    return "installed"
