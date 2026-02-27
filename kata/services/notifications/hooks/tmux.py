"""Tmux hook handler for session events.

Session attach/detach notifications have been removed as they were too noisy.
These functions are kept as no-ops for backward compatibility with existing
tmux hooks that may still call `kata notify-tmux-event`.
"""

from __future__ import annotations


def handle_tmux_event(event_type: str, session_name: str) -> None:
    """No-op. Session event notifications have been removed."""


def register_tmux_hooks(session_name: str) -> None:
    """No-op. Session hook registration has been removed."""


def unregister_tmux_hooks(session_name: str) -> None:
    """No-op. Session hook removal has been removed."""
