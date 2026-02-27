"""Tool-based transcript analyzer for Claude Code hook events.

Classifies notifications by examining which tools were used and
the content of assistant messages, using a 15-message temporal window.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from kata.services.notifications.models import NotificationType

logger = logging.getLogger(__name__)

ACTIVE_TOOLS = frozenset({"Write", "Edit", "Bash", "NotebookEdit", "SlashCommand", "KillShell"})
QUESTION_TOOLS = frozenset({"AskUserQuestion"})
PLANNING_TOOLS = frozenset({"ExitPlanMode", "TodoWrite"})
PASSIVE_TOOLS = frozenset({"Read", "Grep", "Glob", "WebFetch", "WebSearch", "Task"})

_SESSION_LIMIT_PATTERN = re.compile(r"session.?limit", re.IGNORECASE)
_MAX_ASSISTANT_MESSAGES = 15


def parse_transcript_window(transcript_path: str) -> tuple[set[str], list[str]]:
    """Parse JSONL transcript and extract tools + messages after last user message.
    Returns (tool_names, assistant_text_messages) capped at 15 messages.
    """
    path = Path(transcript_path)
    if not path.exists():
        return set(), []

    entries: list[dict] = []
    last_user_idx = -1

    try:
        text = path.read_text()
        lines = text.strip().split("\n")
        for line in lines[-50:]:
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        logger.debug("Failed to read transcript", exc_info=True)
        return set(), []

    for i, entry in enumerate(entries):
        if entry.get("type") in ("human", "user"):
            last_user_idx = i

    tools: set[str] = set()
    messages: list[str] = []
    start = max(0, last_user_idx + 1)

    for entry in entries[start:]:
        if entry.get("type") != "assistant":
            continue

        content = entry.get("message", {}).get("content", "")
        if isinstance(content, str):
            if content.strip():
                messages.append(content.strip())
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name:
                        tools.add(name)
                elif block.get("type") == "text":
                    text = block.get("text", "").strip()
                    if text:
                        messages.append(text)

    messages = messages[-_MAX_ASSISTANT_MESSAGES:]
    return tools, messages


def classify_from_tools_and_text(
    tools: set[str],
    last_messages: list[str],
    has_error: bool = False,
) -> NotificationType:
    """Classify notification type from tool usage and message content.

    Priority: SESSION_LIMIT > ERROR > PLAN_READY > REVIEW_DONE > TASK_COMPLETE
    """
    for msg in last_messages[-3:]:
        if _SESSION_LIMIT_PATTERN.search(msg):
            return NotificationType.SESSION_LIMIT

    if has_error:
        return NotificationType.ERROR

    if tools & PLANNING_TOOLS:
        return NotificationType.PLAN_READY

    has_active = bool(tools & ACTIVE_TOOLS)
    has_passive = bool(tools & PASSIVE_TOOLS)
    total_text = sum(len(m) for m in last_messages)

    if has_passive and not has_active and total_text > 200:
        return NotificationType.REVIEW_DONE

    if has_active:
        return NotificationType.TASK_COMPLETE

    return NotificationType.TASK_COMPLETE


def analyze_transcript(
    transcript_path: str,
    hook_input: dict | None = None,
) -> NotificationType:
    """Full analysis: parse transcript + classify."""
    has_error = bool(hook_input and hook_input.get("error"))
    tools, messages = parse_transcript_window(transcript_path)
    return classify_from_tools_and_text(tools, messages, has_error=has_error)
