"""Git utilities for repository status detection."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kata.core.constants import SUBPROCESS_TIMEOUT


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
