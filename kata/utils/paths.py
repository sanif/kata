"""Path validation utilities for Kata."""

import re
from pathlib import Path

# Conservative matcher for file references in free text (notification bodies).
# Matches an absolute or ~-anchored path, optionally followed by ``:line`` (and
# ``:col``). Relative paths are deliberately excluded: without a known root they
# can't be resolved reliably, and we only ever linkify what exists on disk.
_FILE_REF_RE = re.compile(
    r"""
    (?<![\w./~-])                       # left boundary
    ((?:~|/)[\w./+@%~\-]+)              # anchor (~ or /) then path body
    (?::(\d+))?                         # optional :line
    (?::\d+)?                           # optional :col (ignored)
    """,
    re.VERBOSE,
)


def extract_file_references(text: str) -> list[tuple[str, int | None]]:
    """Extract ``(path, line)`` file references from free text.

    Returns absolute/``~`` paths (with an optional ``:line`` suffix) in order of
    appearance, de-duplicated. Existence is NOT checked here — callers filter to
    real files (off the UI thread). ``line`` is ``None`` when unspecified.
    """
    if not text:
        return []
    seen: set[tuple[str, int | None]] = set()
    out: list[tuple[str, int | None]] = []
    for match in _FILE_REF_RE.finditer(text):
        raw = match.group(1).strip().rstrip(".,;:)]}>")
        if not raw or raw in ("/", "~"):
            continue
        line = int(match.group(2)) if match.group(2) else None
        key = (raw, line)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def resolve_existing_file(path: str) -> Path | None:
    """Expand ``path`` and return it if it points at an existing regular file."""
    try:
        candidate = Path(path).expanduser()
        if candidate.is_file():
            return candidate
    except OSError:
        pass
    return None


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


def sanitize_session_name(name: str) -> str:
    """Sanitize a name for use as a tmux session name.

    tmux session names cannot contain periods or colons.
    This replaces invalid characters with underscores.

    Args:
        name: The name to sanitize

    Returns:
        A valid tmux session name
    """
    # tmux doesn't allow periods or colons in session names
    return name.replace(".", "_").replace(":", "_")
