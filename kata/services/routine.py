"""Morning routine service for batch session management."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from kata.core.config import KATA_CONFIG_DIR
from kata.core.models import Project
from kata.services.registry import get_registry
from kata.services.sessions import launch_session, session_exists, SessionError

# Routine configuration file
ROUTINE_FILE = KATA_CONFIG_DIR / "routine.json"


@dataclass
class RoutineConfig:
    """Configuration for morning routine."""

    groups: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "groups": self.groups,
            "projects": self.projects,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoutineConfig":
        """Create from dictionary."""
        return cls(
            groups=data.get("groups", []),
            projects=data.get("projects", []),
        )


def load_routine() -> RoutineConfig:
    """Load routine configuration from disk.

    Returns:
        RoutineConfig with saved settings
    """
    if not ROUTINE_FILE.exists():
        return RoutineConfig()

    try:
        with open(ROUTINE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return RoutineConfig.from_dict(data)
    except (json.JSONDecodeError, IOError):
        return RoutineConfig()


def save_routine(config: RoutineConfig) -> None:
    """Save routine configuration to disk.

    Args:
        config: Configuration to save
    """
    ROUTINE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(ROUTINE_FILE, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)


def add_group_to_routine(group: str) -> bool:
    """Add a group to the morning routine.

    Args:
        group: Group name to add

    Returns:
        True if added, False if already exists
    """
    config = load_routine()

    if group in config.groups:
        return False

    config.groups.append(group)
    save_routine(config)
    return True


def remove_group_from_routine(group: str) -> bool:
    """Remove a group from the morning routine.

    Args:
        group: Group name to remove

    Returns:
        True if removed, False if not found
    """
    config = load_routine()

    if group not in config.groups:
        return False

    config.groups.remove(group)
    save_routine(config)
    return True


def add_project_to_routine(project_name: str) -> bool:
    """Add a specific project to the morning routine.

    Args:
        project_name: Project name to add

    Returns:
        True if added, False if already exists
    """
    config = load_routine()

    if project_name in config.projects:
        return False

    config.projects.append(project_name)
    save_routine(config)
    return True


def remove_project_from_routine(project_name: str) -> bool:
    """Remove a project from the morning routine.

    Args:
        project_name: Project name to remove

    Returns:
        True if removed, False if not found
    """
    config = load_routine()

    if project_name not in config.projects:
        return False

    config.projects.remove(project_name)
    save_routine(config)
    return True


def clear_routine() -> None:
    """Clear all routine configuration."""
    save_routine(RoutineConfig())


@dataclass
class LaunchResult:
    """Result of launching a project."""

    project: Project
    success: bool
    error: str | None = None
    skipped: bool = False


def launch_group_background(group: str) -> list[LaunchResult]:
    """Launch all projects in a group in background (detached).

    Args:
        group: Group name to launch

    Returns:
        List of launch results for each project
    """
    registry = get_registry()
    projects = registry.list_by_group(group)

    results = []
    for project in projects:
        result = _launch_project_background(project)
        results.append(result)

    return results


def launch_projects_background(project_names: list[str]) -> list[LaunchResult]:
    """Launch specific projects in background.

    Args:
        project_names: List of project names to launch

    Returns:
        List of launch results
    """
    registry = get_registry()
    results = []

    for name in project_names:
        project = registry.get(name) if name in registry else None
        if project is None:
            results.append(
                LaunchResult(
                    project=Project(name=name, path="", group=""),
                    success=False,
                    error="Project not found",
                )
            )
            continue

        result = _launch_project_background(project)
        results.append(result)

    return results


def _launch_project_background(project: Project) -> LaunchResult:
    """Launch a single project in background.

    Args:
        project: Project to launch

    Returns:
        LaunchResult with status
    """
    # Skip if already running
    if session_exists(project.name):
        return LaunchResult(project=project, success=True, skipped=True)

    try:
        launch_session(project)
        return LaunchResult(project=project, success=True)
    except SessionError as e:
        return LaunchResult(project=project, success=False, error=str(e))


def run_morning_routine() -> list[LaunchResult]:
    """Execute the configured morning routine.

    Launches all configured groups and projects in background.

    Returns:
        List of all launch results
    """
    config = load_routine()
    registry = get_registry()
    results: list[LaunchResult] = []

    # Launch projects from configured groups
    for group in config.groups:
        group_results = launch_group_background(group)
        results.extend(group_results)

    # Launch individually configured projects (if not already launched)
    launched_names = {r.project.name for r in results}
    for project_name in config.projects:
        if project_name in launched_names:
            continue

        project = registry.get(project_name) if project_name in registry else None
        if project is None:
            results.append(
                LaunchResult(
                    project=Project(name=project_name, path="", group=""),
                    success=False,
                    error="Project not found",
                )
            )
            continue

        result = _launch_project_background(project)
        results.append(result)

    return results


def get_routine_projects() -> list[Project]:
    """Get all projects that would be launched by the morning routine.

    Returns:
        List of projects in the routine
    """
    config = load_routine()
    registry = get_registry()
    projects: list[Project] = []
    seen_names: set[str] = set()

    # Projects from groups
    for group in config.groups:
        for project in registry.list_by_group(group):
            if project.name not in seen_names:
                projects.append(project)
                seen_names.add(project.name)

    # Individual projects
    for project_name in config.projects:
        if project_name not in seen_names:
            project = registry.get(project_name) if project_name in registry else None
            if project:
                projects.append(project)
                seen_names.add(project_name)

    return projects
