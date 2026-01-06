"""Directory scanner for discovering projects."""

from pathlib import Path

from kata.utils.detection import PROJECT_MARKERS

# Directories to skip when scanning
SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "env",
    ".tox",
    ".nox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".coverage",
    "vendor",
    "target",  # Rust
    "pkg",  # Go
    "bin",
}


def is_project_directory(path: Path) -> bool:
    """Check if a directory appears to be a project root.

    A project is identified by presence of:
    - .git directory (version controlled project)
    - Any project type markers (pyproject.toml, package.json, go.mod, etc.)

    Args:
        path: Directory path to check

    Returns:
        True if directory appears to be a project root
    """
    if not path.is_dir():
        return False

    # Check for .git directory
    if (path / ".git").is_dir():
        return True

    # Check for any project markers
    for markers in PROJECT_MARKERS.values():
        for marker in markers:
            if (path / marker).exists():
                return True

    return False


def scan_directory(
    root: Path,
    max_depth: int = 3,
    include_hidden: bool = False,
) -> list[Path]:
    """Recursively scan for project directories.

    Args:
        root: Root directory to start scanning from
        max_depth: Maximum depth to recurse (default: 3)
        include_hidden: Whether to scan hidden directories (default: False)

    Returns:
        List of paths that appear to be project directories
    """
    projects: list[Path] = []
    root = root.resolve()

    def _scan(current: Path, depth: int) -> None:
        """Recursively scan directory."""
        if depth > max_depth:
            return

        try:
            entries = list(current.iterdir())
        except PermissionError:
            return

        for entry in entries:
            if not entry.is_dir():
                continue

            name = entry.name

            # Skip hidden directories unless explicitly included
            if not include_hidden and name.startswith("."):
                continue

            # Skip known non-project directories
            if name in SKIP_DIRECTORIES:
                continue

            # Check if this is a project
            if is_project_directory(entry):
                projects.append(entry)
                # Don't recurse into project subdirectories
                # (nested projects are rare and usually intentional)
                continue

            # Recurse into subdirectory
            _scan(entry, depth + 1)

    # Check if root itself is a project
    if is_project_directory(root):
        projects.append(root)
    else:
        _scan(root, 1)

    return sorted(projects)


def get_project_info(path: Path) -> dict[str, str | bool]:
    """Get basic information about a project.

    Args:
        path: Path to project directory

    Returns:
        Dictionary with project info
    """
    from kata.utils.detection import detect_project_type
    from kata.utils.paths import get_project_name_from_path

    has_git = (path / ".git").is_dir()
    project_type = detect_project_type(path)

    return {
        "name": get_project_name_from_path(path),
        "path": str(path),
        "type": project_type.value,
        "has_git": has_git,
    }
