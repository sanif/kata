"""Registry service for managing projects."""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from kata.core.config import REGISTRY_FILE, ensure_config_dirs
from kata.core.models import Project
from kata.utils.paths import normalize_path

logger = logging.getLogger(__name__)


class DuplicatePathError(Exception):
    """Raised when attempting to add a project with a duplicate path."""

    pass


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""

    pass


class Registry:
    """Manages the project registry."""

    def __init__(self) -> None:
        """Initialize the registry."""
        self._projects: dict[str, Project] = {}
        # Every name this instance has ever held (loaded, added, updated, or
        # removed). Used by _save to distinguish a project we intentionally
        # deleted from one another process added while we were live.
        self._seen_names: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        ensure_config_dirs()

        if not REGISTRY_FILE.exists():
            self._projects = {}
            self._seen_names = set()
            return

        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            self._projects = {p["name"]: Project.from_dict(p) for p in data.get("projects", [])}
        except (json.JSONDecodeError, KeyError, ValueError):
            # Never destroy the user's data: move the corrupt file aside so the
            # next save starts from a clean slate instead of silently wiping
            # groups, colors, shortcuts, and history.
            self._backup_corrupt_registry()
            self._projects = {}

        self._seen_names = set(self._projects)

    @staticmethod
    def _backup_corrupt_registry() -> None:
        """Move a corrupt registry file aside, preserving the original bytes."""
        try:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = REGISTRY_FILE.with_name(f"{REGISTRY_FILE.name}.corrupt-{ts}")
            counter = 0
            while backup.exists():
                counter += 1
                backup = REGISTRY_FILE.with_name(f"{REGISTRY_FILE.name}.corrupt-{ts}-{counter}")
            os.replace(REGISTRY_FILE, backup)
            logger.warning(
                "registry.json was corrupt; backed it up to %s and started empty", backup
            )
        except OSError:
            logger.warning("registry.json was corrupt and could not be backed up", exc_info=True)

    def reload(self) -> None:
        """Reload registry from disk to pick up external changes."""
        self._load()

    def _save(self) -> None:
        """Save registry to disk atomically, merging concurrent writers.

        Kata runs several processes at once (TUI, strips, daemon). To avoid a
        stale in-memory snapshot silently clobbering another process's save, we
        reload the on-disk state and merge it with ours: this instance is
        authoritative for every project it knows about, and any project another
        process added since we loaded is preserved. A project this instance
        intentionally removed is *not* resurrected (tracked via _seen_names).

        Known limitation: this is not a CRDT. If two live instances hold the
        same project and one deletes it while the other re-saves from its stale
        snapshot, the delete can be lost. That is an acceptable trade against
        the far more common (and destructive) full-registry clobber.
        """
        ensure_config_dirs()

        merged: dict[str, Project] = dict(self._projects)
        if REGISTRY_FILE.exists():
            try:
                disk = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
                for entry in disk.get("projects", []):
                    name = entry.get("name")
                    if not name or name in merged or name in self._seen_names:
                        continue
                    merged[name] = Project.from_dict(entry)
            except (json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError):
                # Corrupt on-disk state: fall back to our own view rather than
                # aborting the save (the corrupt file was already backed up on
                # load; a fresh write here recovers it).
                pass

        data: dict[str, Any] = {
            "version": "1.0",
            "projects": [p.to_dict() for p in merged.values()],
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Unique temp file (not a fixed ".tmp" name) so concurrent writers do
        # not race on the same path; os.replace is atomic on POSIX.
        fd, tmp_name = tempfile.mkstemp(
            dir=str(REGISTRY_FILE.parent), prefix=".registry-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_name, REGISTRY_FILE)
        except Exception:
            Path(tmp_name).unlink(missing_ok=True)
            raise

        self._projects = merged
        self._seen_names.update(merged.keys())

    def add(self, project: Project) -> None:
        """Add a project to the registry.

        Args:
            project: Project to add

        Raises:
            DuplicatePathError: If a project with the same path already exists
        """
        normalized_path = normalize_path(project.path)

        # Check for duplicate path
        for existing in self._projects.values():
            if normalize_path(existing.path) == normalized_path:
                raise DuplicatePathError(f"Project already exists at path: {normalized_path}")

        # Handle name collisions by appending a suffix
        base_name = project.name
        counter = 1
        while project.name in self._projects:
            project.name = f"{base_name}-{counter}"
            project.config = f"{project.name}.yaml"
            counter += 1

        self._projects[project.name] = project
        self._seen_names.add(project.name)
        self._save()

    def remove(self, name: str) -> Project:
        """Remove a project from the registry.

        Args:
            name: Name of the project to remove

        Returns:
            The removed project

        Raises:
            ProjectNotFoundError: If the project doesn't exist
        """
        if name not in self._projects:
            raise ProjectNotFoundError(f"Project not found: {name}")

        project = self._projects.pop(name)
        # Keep the name in _seen_names so the merge in _save does not
        # resurrect it from a stale on-disk copy.
        self._seen_names.add(name)
        self._save()
        return project

    def get(self, name: str) -> Project:
        """Get a project by name.

        Args:
            name: Name of the project

        Returns:
            The project

        Raises:
            ProjectNotFoundError: If the project doesn't exist
        """
        if name not in self._projects:
            raise ProjectNotFoundError(f"Project not found: {name}")
        return self._projects[name]

    def update(self, project: Project) -> None:
        """Update an existing project.

        Args:
            project: Project with updated data

        Raises:
            ProjectNotFoundError: If the project doesn't exist
        """
        if project.name not in self._projects:
            raise ProjectNotFoundError(f"Project not found: {project.name}")

        self._projects[project.name] = project
        self._seen_names.add(project.name)
        self._save()

    def list_all(self) -> list[Project]:
        """List all projects.

        Returns:
            List of all projects
        """
        return list(self._projects.values())

    def get_recent_projects(
        self,
        limit: int = 5,
        current_session: str | None = None,
    ) -> list[Project]:
        """Get most recently opened projects in Alt+Tab order.

        Args:
            limit: Maximum number of projects to return
            current_session: Current session name; if provided, its project
                is moved to position 1 (so position 0 is the "previous" project)

        Returns:
            List of projects sorted by last_opened descending, with None last
        """
        from datetime import datetime

        from kata.utils.paths import sanitize_session_name

        sorted_projects = sorted(
            self._projects.values(),
            key=lambda p: (p.last_opened or datetime.min,),
            reverse=True,
        )
        if current_session and len(sorted_projects) >= 2:
            for i, p in enumerate(sorted_projects):
                if p.name == current_session or sanitize_session_name(p.name) == current_session:
                    sorted_projects.pop(i)
                    sorted_projects.insert(1, p)
                    break
        return sorted_projects[:limit]

    def list_by_group(self, group: str) -> list[Project]:
        """List projects in a specific group.

        Args:
            group: Group name to filter by

        Returns:
            List of projects in the group
        """
        return [p for p in self._projects.values() if p.group == group]

    def get_groups(self) -> list[str]:
        """Get all unique group names.

        Returns:
            List of group names
        """
        return sorted({p.group for p in self._projects.values()})

    def find_by_path(self, path: str | Path) -> Project | None:
        """Find a project by its path.

        Args:
            path: Path to search for

        Returns:
            Project if found, None otherwise
        """
        normalized = normalize_path(path)
        for project in self._projects.values():
            if normalize_path(project.path) == normalized:
                return project
        return None

    def __len__(self) -> int:
        """Return the number of projects."""
        return len(self._projects)

    def __contains__(self, name: str) -> bool:
        """Check if a project exists."""
        return name in self._projects


# Singleton instance
_registry: Registry | None = None


def get_registry() -> Registry:
    """Get the registry singleton.

    Returns:
        The registry instance
    """
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
