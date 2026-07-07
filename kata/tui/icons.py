"""Shared icon and status-indicator tables for the TUI.

Previously ``PROJECT_TYPE_ICONS`` was copy-pasted into four modules and the
session status-indicator dict into three. This is the single source of truth.
"""

from __future__ import annotations

from kata.core.models import SessionStatus

# Project type icons (Nerd Font)
PROJECT_TYPE_ICONS: dict[str, str] = {
    "python": "󰌠",
    "node": "󰎙",
    "rust": "󱘗",
    "go": "󰟓",
    "ruby": "󰴭",
    "generic": "󰉋",
}

# Session status indicators (Rich markup)
STATUS_INDICATORS: dict[SessionStatus, str] = {
    SessionStatus.ACTIVE: "[green]●[/green]",
    SessionStatus.DETACHED: "[yellow]●[/yellow]",
    SessionStatus.IDLE: "[dim]○[/dim]",
}


def project_type_icon(type_value: str) -> str:
    """Return the Nerd Font icon for a project type value (falls back to generic)."""
    return PROJECT_TYPE_ICONS.get(type_value, PROJECT_TYPE_ICONS["generic"])


def status_indicator(status: SessionStatus) -> str:
    """Return the Rich-markup status dot for a session status."""
    return STATUS_INDICATORS.get(status, "[dim]○[/dim]")
