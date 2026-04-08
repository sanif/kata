"""Utilities for extracting Claude Code session information."""

from __future__ import annotations

import json
import logging
from pathlib import Path

SUMMARY_MAX_LEN = 72

_log = logging.getLogger("kata.worktree")


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
    """Extract the last assistant text message from a JSONL session file."""
    last_text = None
    try:
        for line in session_file.read_text().strip().split("\n"):
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
    _log.info("get_current_session_id called with path=%s resolved=%s", worktree_path, resolved)

    # Try to find an active session process for this cwd
    sessions_dir = claude_dir / "sessions"
    if sessions_dir.exists():
        for pid_file in sessions_dir.glob("*.json"):
            try:
                data = json.loads(pid_file.read_text())
                session_cwd = data.get("cwd", "")
                resolved_cwd = str(Path(session_cwd).resolve())
                _log.debug(
                    "  checking pid=%s cwd=%s resolved=%s match=%s",
                    pid_file.stem,
                    session_cwd,
                    resolved_cwd,
                    resolved_cwd == resolved,
                )
                if resolved_cwd == resolved:
                    session_id = data.get("sessionId")
                    _log.info("  FOUND active session: %s", session_id)
                    if session_id:
                        return session_id
            except (json.JSONDecodeError, OSError) as e:
                _log.debug("  error reading %s: %s", pid_file.name, e)
                continue
    else:
        _log.info("  sessions dir does not exist: %s", sessions_dir)

    # Fall back to most recently modified JSONL
    encoded = _encode_cwd(worktree_path)
    session_dir = claude_dir / "projects" / encoded
    _log.info("  fallback: looking in %s", session_dir)

    if not session_dir.exists():
        _log.info("  fallback dir does not exist, returning None")
        return None

    latest = _find_latest_session(session_dir)
    if latest is None:
        _log.info("  no JSONL files found, returning None")
        return None
    _log.info("  fallback found: %s", latest.stem)

    return latest.stem
