"""Shared raw-terminal UI plumbing for kata's tmux popups.

The five raw-mode UIs (switch_strip, notify_strip, worktree_strip, setup_tui,
uninstall_tui) previously each carried their own copy of the terminal frame:
``termios.tcgetattr`` / ``tty.setraw`` / ``finally`` restore, a per-file
``_read_key`` with a slightly different set of recognised escape sequences, and
a verbatim ``_content_row`` border helper. This module consolidates all of that
so the escape-sequence handling and the flicker-free render path exist once.

Rendering is unified on the hidden-cursor in-place repaint used by notify/setup
(home cursor + overwrite) rather than the clear+reprint-with-visible-cursor
approach the switch/worktree strips used, which flickered.
"""

from __future__ import annotations

import json
import os
import select
import sys
import termios
import tty
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.text import Text

__all__ = [
    "is_interactive_terminal",
    "guard_tty",
    "read_key",
    "content_row",
    "raw_screen",
    "FrameRenderer",
    "has_kata_hooks",
]


# ── TTY guards ─────────────────────────────────────────────────────────────


def is_interactive_terminal() -> bool:
    """Return True only when both stdin and stdout are real TTYs.

    Raw-mode UIs call ``termios`` on stdin, which raises ``termios.error`` when
    stdin is a pipe or ``/dev/null`` (CI, ``kata switch-strip < /dev/null``).
    """
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (ValueError, OSError):
        return False


def guard_tty() -> None:
    """Exit(1) with a one-line message when not attached to a terminal.

    Prevents the raw-mode entry points from dumping a ``termios.error``
    traceback when invoked outside an interactive terminal.
    """
    if not is_interactive_terminal():
        print(
            "kata: this command needs an interactive terminal (run it inside a tmux popup).",
            file=sys.stderr,
        )
        raise SystemExit(1)


# ── Input ──────────────────────────────────────────────────────────────────


def read_key(fd: int) -> str:
    """Read one keypress from ``fd`` (already in raw mode) and normalise it.

    Returns a canonical token for the keys any of the five UIs handled:

    * ``"ctrl+space"`` / ``"ctrl+w"`` / ``"ctrl+n"`` — control chords
    * ``"up"`` / ``"down"`` / ``"left"`` / ``"right"`` — arrows (CSI and SS3)
    * ``"shift+tab"`` — back-tab
    * ``"enter"`` / ``"space"`` / ``"tab"`` / ``"backspace"`` / ``"escape"``
    * any other printable character as its decoded string (e.g. ``"a"``, ``"/"``)

    A lone ESC and an unrecognised/aborted escape sequence both map to
    ``"escape"``. Because full escape sequences are consumed here, an arrow key
    pressed during text input no longer cancels the flow nor leaks ``[A`` bytes
    into the next read.
    """
    ch = os.read(fd, 1)
    if ch == b"\x00":
        return "ctrl+space"
    if ch == b"\x17":  # Ctrl+W
        return "ctrl+w"
    if ch == b"\x0e":  # Ctrl+N
        return "ctrl+n"
    if ch == b"\x1b":
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            return "escape"
        seq = os.read(fd, 8)  # drain the whole sequence at once
        if seq in (b"[A", b"OA"):
            return "up"
        if seq in (b"[B", b"OB"):
            return "down"
        if seq in (b"[C", b"OC"):
            return "right"
        if seq in (b"[D", b"OD"):
            return "left"
        if seq == b"[Z":
            return "shift+tab"
        return "escape"
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch == b" ":
        return "space"
    if ch == b"\t":
        return "tab"
    if ch in (b"\x7f", b"\x08"):
        return "backspace"
    if ch == b"\x03":  # Ctrl+C
        return "escape"
    return ch.decode("utf-8", errors="replace")


# ── Rendering ──────────────────────────────────────────────────────────────


def content_row(content: Text, width: int) -> Text:
    """Wrap ``content`` in box side borders, padding to the full panel width."""
    plain_len = len(content.plain)
    pad = max(0, width - 4 - plain_len)
    t = Text()
    t.append("│ ", "dim")
    t.append_text(content)
    t.append(" " * pad)
    t.append(" │", "dim")
    return t


class FrameRenderer:
    """Render Rich ``Text`` lines to a raw-mode-safe ANSI string.

    Uses a ``StringIO``-backed Console so styling survives, and terminates each
    line with ``\\r\\n`` (raw mode does not translate ``\\n`` to CR+LF).
    """

    def __init__(self, width: int) -> None:
        self._console = Console(file=StringIO(), force_terminal=True, width=width)

    def render(self, lines: Iterable[Text]) -> str:
        buf = self._console.file
        buf.seek(0)
        buf.truncate()
        for line in lines:
            self._console.print(line, end="")
            buf.write("\r\n")
        return buf.getvalue()


@contextmanager
def raw_screen(*, hide_cursor: bool = True) -> Iterator[int]:
    """Context manager holding stdin in raw mode for a full-screen UI.

    Hides the cursor and clears the screen on entry; restores termios settings,
    shows the cursor and clears on exit. Yields the stdin file descriptor.

    Callers should invoke :func:`guard_tty` before entering so a non-TTY gets a
    friendly message rather than the ``termios.error`` this would raise.
    """
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if hide_cursor:
            sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
            sys.stdout.flush()
        yield fd
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        if hide_cursor:
            sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
            sys.stdout.flush()


# ── Shared detection ───────────────────────────────────────────────────────


def has_kata_hooks(settings_path: Path) -> bool:
    """Return True if a Claude/Gemini JSON settings file has kata notify hooks.

    Shared by setup_tui and uninstall_tui (previously a verbatim copy in each).
    """
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
        for event_hooks in data.get("hooks", {}).values():
            for entry in event_hooks:
                for h in entry.get("hooks", []):
                    if "kata notify" in h.get("command", ""):
                        return True
    except Exception:
        pass
    return False
