"""Shared utilities for notification hook handlers."""

from __future__ import annotations

from pathlib import Path


def resolve_session_name(cwd: str) -> str:
    """Resolve CWD to a Kata project/session name.

    Looks up the path in the project registry first. Falls back to
    the directory basename if not registered.
    """
    try:
        from kata.services.registry import get_registry

        registry = get_registry()
        project = registry.find_by_path(cwd)
        if project:
            return project.name
    except Exception:
        pass
    return Path(cwd).name if cwd else ""
