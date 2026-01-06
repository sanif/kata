"""Registry service for managing projects."""

import json
from pathlib import Path
from typing import Any

from kata.core.config import REGISTRY_FILE, ensure_config_dirs
from kata.core.models import Project
from kata.utils.paths import normalize_path


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
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        ensure_config_dirs()

        if not REGISTRY_FILE.exists():
            self._projects = {}
            return

        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            self._projects = {
                p["name"]: Project.from_dict(p) for p in data.get("projects", [])
            }
        except (json.JSONDecodeError, KeyError):
            self._projects = {}

    def _save(self) -> None:
        """Save registry to disk."""
        ensure_config_dirs()

        data: dict[str, Any] = {
            "version": "1.0",
            "projects": [p.to_dict() for p in self._projects.values()],
        }

        REGISTRY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

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
                raise DuplicatePathError(
                    f"Project already exists at path: {normalized_path}"
                )

        # Handle name collisions by appending a suffix
        base_name = project.name
        counter = 1
        while project.name in self._projects:
            project.name = f"{base_name}-{counter}"
            project.config = f"{project.name}.yaml"
            counter += 1

        self._projects[project.name] = project
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
        self._save()

    def list_all(self) -> list[Project]:
        """List all projects.

        Returns:
            List of all projects
        """
        return list(self._projects.values())

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
        return sorted(set(p.group for p in self._projects.values()))

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
