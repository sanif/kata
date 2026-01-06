"""Project type detection utilities."""

from pathlib import Path

from kata.core.models import ProjectType


# Project type markers in priority order
PROJECT_MARKERS: dict[ProjectType, list[str]] = {
    ProjectType.PYTHON: ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    ProjectType.NODE: ["package.json"],
    ProjectType.GO: ["go.mod"],
}


def detect_project_type(path: str | Path) -> ProjectType:
    """Detect the project type based on marker files.

    Checks for language-specific files in the directory and returns
    the detected project type. Returns GENERIC if no known markers found.

    Args:
        path: Path to the project directory

    Returns:
        Detected project type
    """
    path_obj = Path(path).expanduser().resolve()

    if not path_obj.is_dir():
        return ProjectType.GENERIC

    # Check each project type's markers in order
    for project_type, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if (path_obj / marker).exists():
                return project_type

    return ProjectType.GENERIC


def get_project_markers(project_type: ProjectType) -> list[str]:
    """Get the marker files for a project type.

    Args:
        project_type: The project type

    Returns:
        List of marker file names
    """
    return PROJECT_MARKERS.get(project_type, [])
