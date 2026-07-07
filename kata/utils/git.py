"""Git utilities for repository status detection."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kata.core.constants import SUBPROCESS_TIMEOUT

# Cap for counting lines of an untracked file (matches the file viewer's cap).
_MAX_COUNT_BYTES = 1024 * 1024


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    """Run a git command and return the result, or None on failure."""
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


@dataclass
class GitStatus:
    """Git repository status information."""

    is_git_repo: bool = False
    branch: str | None = None
    is_dirty: bool = False
    has_staged: bool = False
    has_unstaged: bool = False
    has_untracked: bool = False
    ahead: int = 0
    behind: int = 0

    @property
    def has_changes(self) -> bool:
        """Check if there are any uncommitted changes."""
        return self.has_staged or self.has_unstaged or self.has_untracked


def is_git_repository(path: Path | str) -> bool:
    """Check if a path is inside a git repository.

    Args:
        path: Path to check

    Returns:
        True if path is a git repository
    """
    path = Path(path).resolve()
    result = _run_git(["rev-parse", "--is-inside-work-tree"], path)
    return result is not None and result.returncode == 0 and result.stdout.strip() == "true"


def get_branch_name(path: Path | str) -> str | None:
    """Get the current git branch name.

    Args:
        path: Path to the git repository

    Returns:
        Branch name or None if not a git repo or detached HEAD
    """
    path = Path(path).resolve()

    # First try symbolic-ref for normal branch
    result = _run_git(["symbolic-ref", "--short", "HEAD"], path)
    if result and result.returncode == 0:
        return result.stdout.strip()

    # Fall back to describe for detached HEAD
    result = _run_git(["describe", "--tags", "--exact-match", "HEAD"], path)
    if result and result.returncode == 0:
        return f"tag:{result.stdout.strip()}"

    # Last resort: short SHA
    result = _run_git(["rev-parse", "--short", "HEAD"], path)
    if result and result.returncode == 0:
        return f"({result.stdout.strip()})"

    return None


def is_dirty(path: Path | str) -> bool:
    """Check if the repository has uncommitted changes.

    Args:
        path: Path to the git repository

    Returns:
        True if there are uncommitted changes (staged, unstaged, or untracked)
    """
    path = Path(path).resolve()
    # Check for any changes (staged, unstaged, or untracked)
    result = _run_git(["status", "--porcelain"], path)
    return result is not None and result.returncode == 0 and bool(result.stdout.strip())


def get_git_status(path: Path | str) -> GitStatus:
    """Get comprehensive git status for a repository.

    Args:
        path: Path to the git repository

    Returns:
        GitStatus with all repository information
    """
    path = Path(path).resolve()

    if not is_git_repository(path):
        return GitStatus(is_git_repo=False)

    status = GitStatus(is_git_repo=True)
    status.branch = get_branch_name(path)

    # Get detailed status
    result = _run_git(["status", "--porcelain"], path)
    if result and result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Status format: XY filename
            # X = index status, Y = work tree status
            x_status = line[0] if len(line) > 0 else " "
            y_status = line[1] if len(line) > 1 else " "

            # Check for staged changes (index)
            if x_status not in (" ", "?"):
                status.has_staged = True

            # Check for unstaged changes (work tree)
            if y_status not in (" ", "?"):
                status.has_unstaged = True

            # Check for untracked files
            if x_status == "?" and y_status == "?":
                status.has_untracked = True

    status.is_dirty = status.has_staged or status.has_unstaged or status.has_untracked

    # Get ahead/behind count
    result = _run_git(["rev-list", "--left-right", "--count", "@{upstream}...HEAD"], path)
    if result and result.returncode == 0:
        try:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                status.behind = int(parts[0])
                status.ahead = int(parts[1])
        except ValueError:
            pass

    return status


@dataclass
class ChangedFile:
    """One uncommitted change in a working tree.

    ``added``/``removed`` are line counts from ``git diff --numstat`` (or a
    direct line count for untracked files); ``None`` means binary/unknown.
    """

    path: Path  # absolute
    rel_path: str  # relative to the repo root
    status: str  # M / A / D / U / R
    added: int | None
    removed: int | None
    mtime: float  # 0.0 when the file no longer exists (deletions)


def _status_letter(x: str, y: str) -> str:
    """Collapse a porcelain XY pair into a single display letter."""
    if x == "?" or y == "?":
        return "U"
    if "R" in (x, y):
        return "R"
    if "D" in (x, y):
        return "D"
    if "A" in (x, y):
        return "A"
    return "M"


def _normalize_numstat_path(raw: str) -> str:
    """Resolve rename syntax in a numstat path to the new name.

    Handles both ``old => new`` and the brace form ``dir/{old => new}/file``.
    """
    if " => " not in raw:
        return raw
    if "{" in raw:
        collapsed = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", raw)
        return collapsed.replace("//", "/")
    return raw.split(" => ")[-1]


def _parse_numstat(output: str) -> dict[str, tuple[int | None, int | None]]:
    """Parse ``git diff --numstat`` output into ``{rel_path: (added, removed)}``."""
    stats: dict[str, tuple[int | None, int | None]] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a_raw, r_raw, raw_path = parts
        rel = _normalize_numstat_path(raw_path.strip().strip('"'))
        added = None if a_raw == "-" else int(a_raw)
        removed = None if r_raw == "-" else int(r_raw)
        if rel in stats:
            prev_a, prev_r = stats[rel]
            if not (prev_a is None and added is None):
                added = (prev_a or 0) + (added or 0)
            if not (prev_r is None and removed is None):
                removed = (prev_r or 0) + (removed or 0)
        stats[rel] = (added, removed)
    return stats


def _count_file_lines(path: Path) -> int | None:
    """Count lines in a file (capped at ~1MB); ``None`` for binary/unreadable."""
    try:
        with path.open("rb") as fh:
            chunk = fh.read(_MAX_COUNT_BYTES)
    except OSError:
        return None
    if b"\x00" in chunk[:8192]:
        return None
    if not chunk:
        return 0
    return chunk.count(b"\n") + (0 if chunk.endswith(b"\n") else 1)


def collect_uncommitted_changes(path: Path | str) -> list[ChangedFile] | None:
    """Collect all uncommitted changes (staged + unstaged + untracked).

    Returns ``None`` when ``path`` is not inside a git repository. Files are
    sorted by working-tree mtime, newest first (deleted files sink to the
    bottom). Blocking — meant to run in a worker thread.
    """
    path = Path(path).resolve()
    top = _run_git(["rev-parse", "--show-toplevel"], path)
    if top is None or top.returncode != 0:
        return None
    root = Path(top.stdout.strip())

    status = _run_git(["status", "--porcelain", "-uall"], root)
    if status is None or status.returncode != 0:
        return None

    # Line counts: unstaged + staged numstat merged per file.
    stats: dict[str, tuple[int | None, int | None]] = {}
    for extra in ([], ["--cached"]):
        numstat = _run_git(["diff", *extra, "--numstat"], root)
        if numstat is None or numstat.returncode != 0:
            continue
        for rel, (a, r) in _parse_numstat(numstat.stdout).items():
            if rel in stats:
                prev_a, prev_r = stats[rel]
                if not (prev_a is None and a is None):
                    a = (prev_a or 0) + (a or 0)
                if not (prev_r is None and r is None):
                    r = (prev_r or 0) + (r or 0)
            stats[rel] = (a, r)

    changes: list[ChangedFile] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        x, y, rest = line[0], line[1], line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ")[-1]
        rel = rest.strip().strip('"')
        if not rel:
            continue
        letter = _status_letter(x, y)
        abs_path = root / rel

        if letter == "U":
            added: int | None = _count_file_lines(abs_path)
            removed: int | None = 0 if added is not None else None
        else:
            added, removed = stats.get(rel, (None, None))

        try:
            mtime = abs_path.stat().st_mtime
        except OSError:
            mtime = 0.0

        changes.append(
            ChangedFile(
                path=abs_path,
                rel_path=rel,
                status=letter,
                added=added,
                removed=removed,
                mtime=mtime,
            )
        )

    changes.sort(key=lambda f: f.mtime, reverse=True)
    return changes


def get_uncommitted_diff(path: Path | str, rel_path: str) -> str | None:
    """Return the unified diff (staged + unstaged vs HEAD) for one file.

    Falls back to index/worktree diffs when HEAD doesn't exist yet (fresh
    repo). ``None`` on git failure. Blocking — run in a worker thread.
    """
    path = Path(path).resolve()
    result = _run_git(["diff", "HEAD", "--", rel_path], path)
    if result is not None and result.returncode == 0:
        return result.stdout
    # No HEAD yet (no commits): concatenate staged and unstaged diffs.
    parts: list[str] = []
    for extra in (["--cached"], []):
        result = _run_git(["diff", *extra, "--", rel_path], path)
        if result is not None and result.returncode == 0 and result.stdout:
            parts.append(result.stdout)
    if parts:
        return "".join(parts)
    return None


def format_git_indicator(status: GitStatus) -> str:
    """Format git status as a compact indicator string.

    Args:
        status: GitStatus object

    Returns:
        Formatted string like "main*" or "main↑2↓1"
    """
    if not status.is_git_repo or not status.branch:
        return ""

    parts = [status.branch]

    # Add dirty indicator
    if status.is_dirty:
        parts.append("*")

    # Add ahead/behind indicators
    if status.ahead > 0:
        parts.append(f"↑{status.ahead}")
    if status.behind > 0:
        parts.append(f"↓{status.behind}")

    return "".join(parts)


def format_git_indicator_rich(status: GitStatus) -> str:
    """Format git status with Rich markup for TUI display.

    Args:
        status: GitStatus object

    Returns:
        Formatted string with Rich color markup
    """
    if not status.is_git_repo or not status.branch:
        return ""

    parts = [f"[cyan]{status.branch}[/cyan]"]

    # Add dirty indicator
    if status.is_dirty:
        parts.append("[yellow]*[/yellow]")

    # Add ahead/behind indicators
    if status.ahead > 0:
        parts.append(f"[green]↑{status.ahead}[/green]")
    if status.behind > 0:
        parts.append(f"[red]↓{status.behind}[/red]")

    return "".join(parts)
