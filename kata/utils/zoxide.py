"""Zoxide integration utilities for directory frequency tracking."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ZoxideEntry:
    """A directory entry from zoxide database."""

    path: str
    score: float
    name: str

    @property
    def exists(self) -> bool:
        """Check if the directory still exists."""
        return Path(self.path).is_dir()


def is_zoxide_available() -> bool:
    """Check if zoxide is installed and available.

    Returns:
        True if zoxide is installed, False otherwise
    """
    return shutil.which("zoxide") is not None


def query_zoxide(
    limit: int = 50,
    exclude_paths: set[str] | None = None,
) -> list[ZoxideEntry]:
    """Query zoxide database for frequently visited directories.

    Args:
        limit: Maximum number of entries to return
        exclude_paths: Set of paths to exclude from results (e.g., registered projects)

    Returns:
        List of ZoxideEntry objects sorted by score (highest first)
    """
    if not is_zoxide_available():
        return []

    exclude_paths = exclude_paths or set()

    try:
        # Query zoxide for all entries with scores
        # zoxide query -l -s outputs: "score path" per line
        result = subprocess.run(
            ["zoxide", "query", "-l", "-s"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        entries: list[ZoxideEntry] = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            # Parse "score path" format (score may have decimals)
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue

            try:
                score = float(parts[0])
            except ValueError:
                continue

            path = parts[1].strip()

            # Skip excluded paths (registered projects)
            if path in exclude_paths:
                continue

            # Skip home directory itself
            home = str(Path.home())
            if path == home:
                continue

            # Get the directory name
            name = Path(path).name

            entry = ZoxideEntry(path=path, score=score, name=name)

            # Only include directories that still exist
            if entry.exists:
                entries.append(entry)

                # Stop if we have enough entries
                if len(entries) >= limit:
                    break

        return entries

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
