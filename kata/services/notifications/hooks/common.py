"""Shared utilities for notification hook handlers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from kata.services.notifications import notify
from kata.services.notifications.dispatch.dedup import check_and_acquire
from kata.services.notifications.dispatch.macos import TYPE_TITLES, get_git_branch
from kata.services.notifications.dispatch.state import (
    is_suppressed,
    load_session_state,
    update_session_state,
)
from kata.services.notifications.dispatch.summary import generate_summary
from kata.services.notifications.models import NotificationSource, NotificationType

# Claude Code always stamps every hook payload with this key; its values are
# Claude-specific event names. Gemini CLI and Codex payloads never carry it.
_CLAUDE_EVENT_NAMES = frozenset(
    {
        "Notification",
        "Stop",
        "SubagentStop",
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "PreCompact",
        "SessionStart",
        "SessionEnd",
    }
)


def resolve_session_name(cwd: str) -> str:
    """Resolve CWD to a Kata project/session name.

    Looks up the path in the project registry first. Falls back to
    the directory basename if not registered.
    """
    try:
        from kata.services.registry import get_registry

        registry = get_registry()
        project = registry.find_by_path(cwd)
        if project:
            return project.name
    except Exception:
        pass
    return Path(cwd).name if cwd else ""


def identify_notification_source(data: dict[str, Any]) -> NotificationSource:
    """Identify which AI CLI produced a shared ``notification`` hook payload.

    The ``notify-hook notification`` event name is used by both Claude Code and
    Gemini CLI, so the payload shape must disambiguate them. Codex is included
    for completeness even though it is routed by its own ``codex`` event name.

    Decision table (evaluated top to bottom, first match wins):

    | Discriminator                               | Source        |
    |---------------------------------------------|---------------|
    | ``hook_event_name`` is a known Claude event | CLAUDE_CODE   |
    | ``hook_event_name`` present (any value)     | CLAUDE_CODE   |
    | ``prompt_response`` key present             | GEMINI        |
    | ``type`` present, no session/transcript     | CODEX         |
    | (fallback)                                  | CLAUDE_CODE   |

    Rationale:
    * Claude Code stamps ``hook_event_name`` on *every* payload (the previous
      ``"hook_event_name" in data`` check misrouted all Claude payloads to
      Gemini). Its presence is therefore a strong positive signal for Claude,
      never for Gemini.
    * Gemini CLI payloads carry ``prompt_response`` (the model's final text) and
      do not include ``hook_event_name``.
    * Codex notify payloads carry a top-level ``type`` (e.g.
      ``"agent-turn-complete"``) and lack both ``hook_event_name`` and a
      Claude-style ``session_id``/``transcript_path`` pair.
    * The safe fallback is Claude Code, matching prior behavior for unknown
      payloads.
    """
    if not isinstance(data, dict):
        return NotificationSource.CLAUDE_CODE

    event_name = data.get("hook_event_name")
    if isinstance(event_name, str) and event_name:
        # Presence of hook_event_name is Claude-specific regardless of value.
        return NotificationSource.CLAUDE_CODE

    if "prompt_response" in data:
        return NotificationSource.GEMINI

    if "type" in data and not (data.get("session_id") and data.get("transcript_path")):
        return NotificationSource.CODEX

    return NotificationSource.CLAUDE_CODE


def run_hook_pipeline(
    *,
    source: NotificationSource,
    event_type: str,
    session_id: str,
    classify: Callable[[], NotificationType],
    settings: Any,
    cwd: str = "",
    transcript_path: str = "",
    last_message: str = "",
    extra_metadata: dict[str, Any] | None = None,
    default_title: str = "Notification",
) -> None:
    """Shared dispatch pipeline: dedup -> classify -> suppress -> notify -> state.

    Payload parsing and the ``classify`` decision live in each source module;
    this function owns the behavior that used to be copy-pasted across the
    Claude Code, Gemini, and Codex handlers.

    ``classify`` is called only after deduplication so that expensive work
    (e.g. transcript analysis) is skipped for duplicate events.
    """
    # 1. Dedup — single atomic acquire (no two-phase blind window).
    if not check_and_acquire(session_id, event_type):
        return

    # 2. Classify (deferred until after dedup).
    notification_type = classify()

    # 3. Suppression check.
    state = load_session_state(session_id)
    if is_suppressed(
        notification_type,
        state,
        suppress_dup=settings.notifications_suppress_duplicate_seconds,
        suppress_q_task=settings.notifications_suppress_question_after_task_seconds,
        suppress_q_any=settings.notifications_suppress_question_after_any_seconds,
    ):
        return

    # 4. Build notification.
    summary = generate_summary(last_message) if last_message else ""
    branch = get_git_branch(cwd)
    session_name = resolve_session_name(cwd)
    title = TYPE_TITLES.get(notification_type, default_title)

    metadata: dict[str, Any] = {
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": transcript_path,
        "branch": branch,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    # 5. Dispatch.
    notify(
        type=notification_type,
        source=source,
        title=title,
        body=summary,
        session_name=session_name,
        metadata=metadata,
    )

    # 6. Update session state.
    update_session_state(session_id, notification_type)
