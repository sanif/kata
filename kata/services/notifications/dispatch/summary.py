"""Notification summary generator — cleans markdown and truncates."""

from __future__ import annotations

import re

_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_HEADER = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(.+?)\*")
_BACKTICK = re.compile(r"`([^`]+)`")
_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


def generate_summary(text: str, max_length: int = 200) -> str:
    """Clean markdown formatting and truncate for notification display."""
    if not text:
        return ""

    result = _CODE_BLOCK.sub("", text)
    result = _HEADER.sub("", result)
    result = _BOLD.sub(r"\1", result)
    result = _ITALIC.sub(r"\1", result)
    result = _BACKTICK.sub(r"\1", result)
    result = _BULLET.sub("", result)
    result = _WHITESPACE.sub(" ", result).strip()

    if len(result) > max_length:
        result = result[: max_length - 1] + "…"

    return result
