"""Utilities for extracting Claude Code session information."""

from __future__ import annotations

import json
from pathlib import Path

SUMMARY_MAX_LEN = 72


def _encode_cwd(path: str) -> str:
    """Encode a working directory path the way Claude Code does.

    Claude replaces ALL non-alphanumeric characters with '-'.
    """
    import re

    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def _find_latest_session(session_dir: Path) -> Path | None:
    """Find the most recently modified .jsonl file in a directory."""
    jsonl_files = list(session_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None
    return max(jsonl_files, key=lambda f: f.stat().st_mtime)


def _extract_last_assistant_text(session_file: Path) -> str | None:
    """Extract the last assistant text message from a JSONL session file.

    Streams the file line by line rather than reading it whole — Claude Code
    session transcripts can grow to hundreds of MB, and loading one into a
    single string would spike memory for a one-line summary.
    """
    last_text = None
    try:
        with session_file.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue

                message = entry.get("message", {})
                content = message.get("content", "")

                if isinstance(content, str) and content.strip():
                    last_text = content.strip()
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text:
                                last_text = text
    except (OSError, UnicodeDecodeError):
        pass
    return last_text


def get_session_summary(
    worktree_path: str,
    claude_dir: Path | None = None,
) -> str | None:
    """Get a 1-line summary of the most recent Claude session for a path."""
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    encoded = _encode_cwd(worktree_path)
    session_dir = claude_dir / "projects" / encoded

    if not session_dir.exists():
        return None

    latest = _find_latest_session(session_dir)
    if latest is None:
        return None

    text = _extract_last_assistant_text(latest)
    if text is None:
        return None

    first_line = text.split("\n")[0]
    if len(first_line) > SUMMARY_MAX_LEN:
        return first_line[: SUMMARY_MAX_LEN - 1] + "\u2026"
    return first_line


# Claude Code tools whose invocations edit files on disk.
_EDIT_TOOL_NAMES = frozenset({"Edit", "Write", "NotebookEdit"})


def get_session_edited_files(
    project_path: str | Path,
    claude_dir: Path | None = None,
) -> set[Path]:
    """Collect files edited by the most recent Claude Code session for a path.

    Streams the latest session JSONL line by line (same memory discipline as
    ``_extract_last_assistant_text`` — transcripts can be hundreds of MB) and
    gathers ``file_path``/``notebook_path`` inputs of Edit/Write/NotebookEdit
    ``tool_use`` blocks. Returns resolved absolute paths; empty set when no
    session exists or nothing was edited.
    """
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    encoded = _encode_cwd(str(project_path))
    session_dir = claude_dir / "projects" / encoded
    if not session_dir.exists():
        return set()

    latest = _find_latest_session(session_dir)
    if latest is None:
        return set()

    edited: set[Path] = set()
    try:
        with latest.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue

                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue

                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in _EDIT_TOOL_NAMES:
                        continue
                    tool_input = block.get("input")
                    if not isinstance(tool_input, dict):
                        continue
                    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
                    if isinstance(file_path, str) and file_path:
                        try:
                            edited.add(Path(file_path).resolve())
                        except OSError:
                            continue
    except (OSError, UnicodeDecodeError):
        pass
    return edited


def get_current_session_id(
    worktree_path: str,
    claude_dir: Path | None = None,
) -> str | None:
    """Get the session ID of the active Claude session for a path.

    First checks ~/.claude/sessions/*.json for a running process whose cwd
    matches. Falls back to the most recently modified JSONL if no active
    process is found.
    """
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    resolved = str(Path(worktree_path).resolve())

    # Try to find an active session process for this cwd
    sessions_dir = claude_dir / "sessions"
    if sessions_dir.exists():
        for pid_file in sessions_dir.glob("*.json"):
            try:
                data = json.loads(pid_file.read_text())
                session_cwd = data.get("cwd", "")
                resolved_cwd = str(Path(session_cwd).resolve())
                if resolved_cwd == resolved:
                    session_id = data.get("sessionId")
                    if session_id:
                        return session_id
            except (json.JSONDecodeError, OSError):
                continue

    # Fall back to most recently modified JSONL
    encoded = _encode_cwd(worktree_path)
    session_dir = claude_dir / "projects" / encoded

    if not session_dir.exists():
        return None

    latest = _find_latest_session(session_dir)
    if latest is None:
        return None

    return latest.stem
