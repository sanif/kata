"""Notification dispatch pipeline.

Modules:
    analyzer  — Tool-based transcript classification
    audio     — Per-type MP3 sound playback via afplay
    dedup     — Two-phase lock deduplication
    macos     — macOS native notification dispatcher
    state     — Per-session state tracking and suppression
    summary   — Markdown-aware summary generator
"""
