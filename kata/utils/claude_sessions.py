"""Utilities for extracting Claude Code session information."""

from __future__ import annotations

import json
from pathlib import Path

SUMMARY_MAX_LEN = 72


def _encode_cwd(path: str) -> str:
    """Encode a working directory path the way Claude Code does."""
    return path.replace("/", "-")


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
    """Get the session ID of the most recent Claude session for a path."""
    if claude_dir is None:
        claude_dir = Path.home() / ".claude"

    encoded = _encode_cwd(worktree_path)
    session_dir = claude_dir / "projects" / encoded

    if not session_dir.exists():
        return None

    latest = _find_latest_session(session_dir)
    if latest is None:
        return None

    return latest.stem
