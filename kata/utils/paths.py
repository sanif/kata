"""Path validation utilities for Kata."""

from pathlib import Path


class PathValidationError(Exception):
    """Raised when a path fails validation."""

    pass


def validate_project_path(path: str | Path) -> Path:
    """Validate that a path exists and is a directory.

    Args:
        path: Path to validate

    Returns:
        Resolved Path object

    Raises:
        PathValidationError: If path doesn't exist or isn't a directory
    """
    path_obj = Path(path).expanduser().resolve()

    if not path_obj.exists():
        raise PathValidationError(f"Path does not exist: {path_obj}")

    if not path_obj.is_dir():
        raise PathValidationError(f"Path is not a directory: {path_obj}")

    return path_obj


def normalize_path(path: str | Path) -> str:
    """Normalize a path to absolute form with user expansion.

    Args:
        path: Path to normalize

    Returns:
        Absolute path string
    """
    return str(Path(path).expanduser().resolve())


def get_project_name_from_path(path: str | Path) -> str:
    """Extract project name from a path (directory name).

    Args:
        path: Path to extract name from

    Returns:
        Directory name as project name
    """
    return Path(path).expanduser().resolve().name
