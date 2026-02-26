"""Claude Code hook handler — transcript parsing and event classification."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from kata.services.notifications import notify
from kata.services.notifications.models import NotificationSource, NotificationType

logger = logging.getLogger(__name__)

# Patterns for classification
_QUESTION_PATTERNS = re.compile(r"\?(?:\s|$)", re.MULTILINE)
_ERROR_PATTERNS = re.compile(
    r"(?:error|failed|exception|rate.?limit|429|500|502|503|timeout)",
    re.IGNORECASE,
)
_SESSION_LIMIT_PATTERN = re.compile(r"session.?limit", re.IGNORECASE)
_PLAN_TOOLS = {"ExitPlanMode"}


def parse_transcript(transcript_path: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Parse a JSONL transcript file.

    Returns:
        Tuple of (recent_assistant_messages, recent_tool_uses)
    """
    messages: list[dict[str, Any]] = []
    tools: list[dict[str, str]] = []

    path = Path(transcript_path)
    if not path.exists():
        return messages, tools

    try:
        lines = path.read_text().strip().split("\n")
        # Only look at the last 20 lines for performance
        for line in lines[-20:]:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = entry.get("type", "")
            message = entry.get("message", {})

            if msg_type == "assistant":
                content = message.get("content", "")
                if isinstance(content, str):
                    messages.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": block.get("text", ""),
                                    }
                                )
                            elif block.get("type") == "tool_use":
                                tools.append({"name": block.get("name", "")})
    except Exception:
        logger.debug("Failed to parse transcript", exc_info=True)

    return messages, tools


def classify_event(
    messages: list[dict[str, Any]],
    tools: list[dict[str, str]],
) -> NotificationType:
    """Classify the event type from transcript content.

    Analyzes recent assistant messages and tool usage to determine
    what kind of notification to send.
    """
    tool_names = {t["name"] for t in tools}

    # Check for plan mode exit
    if tool_names & _PLAN_TOOLS:
        return NotificationType.PLAN_READY

    # Analyze the last assistant message
    last_text = ""
    for msg in reversed(messages):
        if msg.get("content", "").strip():
            last_text = msg["content"]
            break

    if not last_text:
        return NotificationType.TASK_COMPLETE

    # Session limit
    if _SESSION_LIMIT_PATTERN.search(last_text):
        return NotificationType.SESSION_LIMIT

    # Error detection
    if _ERROR_PATTERNS.search(last_text) and len(last_text) < 500:
        return NotificationType.ERROR

    # Question detection — short message ending with question mark
    if _QUESTION_PATTERNS.search(last_text) and len(last_text) < 300:
        return NotificationType.QUESTION

    # Default to task complete
    return NotificationType.TASK_COMPLETE


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

    # Fallback: use directory name
    return Path(cwd).name


def handle_claude_stop(stdin_data: str) -> None:
    """Handle a Claude Code Stop/SubagentStop hook event.

    Called by `kata notify-claude-stop` with JSON context from stdin.
    """
    try:
        context = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError:
        logger.debug("Invalid JSON from Claude Code hook stdin")
        return

    transcript_path = context.get("transcript_path", "")
    cwd = context.get("cwd", "")
    session_id = context.get("session_id", "")

    messages, tools = parse_transcript(transcript_path)

    if not messages:
        return

    event_type = classify_event(messages, tools)
    session_name = _resolve_session_name(cwd) if cwd else ""

    # Build title based on type
    titles = {
        NotificationType.TASK_COMPLETE: "Task Completed",
        NotificationType.QUESTION: "Question Asked",
        NotificationType.PLAN_READY: "Plan Ready for Review",
        NotificationType.REVIEW_DONE: "Review Complete",
        NotificationType.ERROR: "Error Occurred",
        NotificationType.SESSION_LIMIT: "Session Limit Reached",
    }
    title = titles.get(event_type, "Claude Code Event")

    # Extract body from last message
    body = ""
    for msg in reversed(messages):
        text = msg.get("content", "").strip()
        if text:
            body = text[:200]  # Truncate for notification
            break

    notify(
        type=event_type,
        source=NotificationSource.CLAUDE_CODE,
        title=title,
        body=body,
        session_name=session_name,
        metadata={
            "session_id": session_id,
            "cwd": cwd,
            "transcript_path": transcript_path,
        },
    )


def setup_hooks() -> None:
    """Set up Claude Code hooks in ~/.claude/settings.json."""
    settings_path = Path.home() / ".claude" / "settings.json"

    # Load existing settings
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}

    hooks = existing.setdefault("hooks", {})

    # Define Kata hooks
    kata_hook = {
        "matcher": "",
        "hooks": [{"type": "command", "command": "kata notify-claude-stop"}],
    }

    # Add to Stop and SubagentStop (avoid duplicates)
    for event in ("Stop", "SubagentStop"):
        event_hooks = hooks.setdefault(event, [])
        # Check if our hook already exists
        already_exists = any(
            any(h.get("command", "").startswith("kata notify") for h in entry.get("hooks", []))
            for entry in event_hooks
        )
        if not already_exists:
            event_hooks.append(kata_hook)

    # Write back
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
