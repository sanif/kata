"""Service for managing git worktrees within kata projects."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import WorktreeInfo, WorktreeStatus

# Reuse the single git runner from utils.git rather than a verbatim copy.
# Imported (not re-exported) so tests can still patch
# ``kata.services.worktrees._run_git``.
from kata.utils.git import _run_git, get_branch_name, get_git_status

logger = logging.getLogger(__name__)

WORKTREES_DIR = ".worktrees"
METADATA_FILE = ".kata-worktrees.json"

# Worktree names become path components under .worktrees/, so they must not be
# able to escape the project or otherwise abuse the filesystem.
_MAX_WORKTREE_NAME_LEN = 100

_SHARED_SYMLINKS = [".env", "node_modules", ".venv"]


class WorktreeError(Exception):
    """Raised when a worktree operation fails."""


def _validate_worktree_name(name: str) -> None:
    """Reject worktree names that are unsafe to use as a path component.

    Args:
        name: Candidate worktree name

    Raises:
        WorktreeError: If the name is empty, path-traversing, or otherwise
            unsafe.
    """
    if not name or not name.strip():
        raise WorktreeError("Worktree name cannot be empty")
    if len(name) > _MAX_WORKTREE_NAME_LEN:
        raise WorktreeError(f"Worktree name too long (max {_MAX_WORKTREE_NAME_LEN} characters)")
    if name.startswith("-"):
        raise WorktreeError("Worktree name cannot start with '-'")
    for bad in ("/", "\\", "..", "~"):
        if bad in name:
            raise WorktreeError(f"Worktree name cannot contain '{bad}'")


def _metadata_path(project_path: Path) -> Path:
    return project_path / WORKTREES_DIR / METADATA_FILE


def _backup_corrupt_metadata(path: Path) -> None:
    """Move a corrupt worktree metadata file aside instead of losing it."""
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.corrupt-{ts}")
        counter = 0
        while backup.exists():
            counter += 1
            backup = path.with_name(f"{path.name}.corrupt-{ts}-{counter}")
        os.replace(path, backup)
        logger.warning("Worktree metadata was corrupt; backed it up to %s", backup)
    except OSError:
        logger.warning("Worktree metadata was corrupt and could not be backed up", exc_info=True)


def _load_metadata(project_path: Path) -> list[WorktreeInfo]:
    path = _metadata_path(project_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [WorktreeInfo.from_dict(w) for w in data.get("worktrees", [])]
    except (json.JSONDecodeError, KeyError, ValueError):
        # Don't silently degrade to "no worktrees" and then overwrite: preserve
        # the corrupt file so it can be recovered.
        _backup_corrupt_metadata(path)
        return []


def _save_metadata(project_path: Path, worktrees: list[WorktreeInfo]) -> None:
    path = _metadata_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({"worktrees": [w.to_dict() for w in worktrees]}, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".kata-worktrees-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _ensure_gitignore(project_path: Path) -> None:
    gitignore = project_path / ".gitignore"
    entry = ".worktrees/"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.rstrip("/") == ".worktrees":
                return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{entry}\n"
        gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")


def _symlink_shared_files(project_path: Path, wt_path: Path) -> None:
    for name in _SHARED_SYMLINKS:
        source = project_path / name
        target = wt_path / name
        if source.exists() and not target.exists():
            target.symlink_to(source)

    # Symlink .kata.yaml (the primary kata config — dotfile, not matched by *.yaml)
    kata_config = project_path / ".kata.yaml"
    if kata_config.exists():
        target = wt_path / ".kata.yaml"
        if not target.exists():
            target.symlink_to(kata_config)


def create_worktree(
    project_path: Path | str,
    name: str,
    branch: str | None = None,
    context_mode: str = "fresh",
    source_session_id: str | None = None,
) -> WorktreeInfo:
    _validate_worktree_name(name)
    project_path = Path(project_path).resolve()
    branch = branch or name
    wt_path = f"{WORKTREES_DIR}/{name}"
    abs_wt_path = project_path / wt_path

    existing = _load_metadata(project_path)
    if any(w.name == name for w in existing):
        raise WorktreeError(f"Worktree '{name}' already exists")

    _ensure_gitignore(project_path)

    result = _run_git(["worktree", "add", str(abs_wt_path), "-b", branch], project_path)
    if result is None or result.returncode != 0:
        stderr = result.stderr if result else "git command failed"
        raise WorktreeError(f"Failed to create worktree: {stderr}")

    _symlink_shared_files(project_path, abs_wt_path)

    info = WorktreeInfo(
        name=name,
        branch=branch,
        path=wt_path,
        created_at=datetime.now(),
        context_mode=context_mode,
        source_session_id=source_session_id,
    )
    existing.append(info)
    _save_metadata(project_path, existing)
    return info


def delete_worktree(project_path: Path | str, name: str, force: bool = False) -> str | None:
    """Delete a worktree and its branch.

    Removal is ordered so we never cripple a worktree we can't actually remove:
    git removal is attempted *first*, and only on success do we clean up any
    kata-generated leftovers. If git removal fails (locked worktree, submodule,
    etc.) the worktree is left fully intact and a WorktreeError is raised.

    Returns:
        A warning string if the worktree was removed but its branch could not
        be deleted, otherwise None.
    """
    project_path = Path(project_path).resolve()
    if name == "main":
        raise WorktreeError("Cannot delete main worktree")
    _validate_worktree_name(name)

    existing = _load_metadata(project_path)
    wt = next((w for w in existing if w.name == name), None)
    if wt is None:
        raise WorktreeError(f"Worktree '{name}' not found")
    # Guard against a poisoned metadata entry driving rmtree/remove outside the
    # project tree.
    _validate_worktree_name(wt.name)

    abs_wt_path = project_path / wt.path

    # Kill any tmux session using this worktree (safe — no user data at risk).
    _kill_worktree_session(abs_wt_path)

    # Remove via git FIRST. --force retry handles untracked/modified files
    # (including kata's own symlinks); doing this before touching leftovers
    # means a failed removal leaves the worktree usable.
    args = ["worktree", "remove", str(abs_wt_path)]
    if force:
        args.append("--force")
    result = _run_git(args, project_path)

    if result and result.returncode != 0 and not force:
        stderr = result.stderr or ""
        if "untracked" in stderr or "modified" in stderr or "contains modified" in stderr:
            result = _run_git(["worktree", "remove", "--force", str(abs_wt_path)], project_path)

    if result is None or result.returncode != 0:
        stderr = result.stderr if result else "git command failed"
        raise WorktreeError(f"Failed to remove worktree: {stderr}")

    # git removed the working tree; clean any straggler files best-effort.
    _cleanup_worktree_files(abs_wt_path)

    # Delete the branch. Try safe delete, escalate to -D only when force was
    # requested, and surface (rather than swallow) a failure so an orphan
    # branch doesn't silently block recreating the name.
    warning: str | None = None
    del_result = _run_git(["branch", "-d", wt.branch], project_path)
    if del_result is None or del_result.returncode != 0:
        if force:
            del_result = _run_git(["branch", "-D", wt.branch], project_path)
        if del_result is None or del_result.returncode != 0:
            detail = (
                del_result.stderr.strip() if del_result and del_result.stderr else "unknown error"
            )
            warning = f"Worktree removed but branch '{wt.branch}' was not deleted: {detail}"
            logger.warning(warning)

    existing = [w for w in existing if w.name != name]
    _save_metadata(project_path, existing)
    return warning


def _cleanup_worktree_files(wt_path: Path) -> None:
    """Remove kata-generated files from a worktree before deletion."""
    import shutil

    # Remove .claude/ dir we created for context seeding
    claude_dir = wt_path / ".claude"
    if claude_dir.exists():
        shutil.rmtree(claude_dir, ignore_errors=True)

    # Remove symlinks we created
    for name in [*_SHARED_SYMLINKS, ".kata.yaml"]:
        target = wt_path / name
        if target.is_symlink():
            target.unlink()


def _kill_worktree_session(wt_path: Path) -> None:
    """Kill any tmux session whose start directory matches this worktree."""
    try:
        result = subprocess.run(
            [
                "tmux",
                "list-sessions",
                "-F",
                "#{session_name}|#{session_path}",
            ],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if result.returncode != 0:
            return

        wt_str = str(wt_path.resolve())
        for line in result.stdout.strip().split("\n"):
            if "|" not in line:
                continue
            # Session names can contain "|"; the path is the final field.
            session_name, _, session_path = line.rpartition("|")
            if session_path == wt_str:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True,
                    timeout=SUBPROCESS_TIMEOUT,
                )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def list_worktrees(project_path: Path | str) -> list[WorktreeStatus]:
    project_path = Path(project_path).resolve()

    main_branch = get_branch_name(project_path) or "main"
    main_git = get_git_status(project_path)
    main_info = WorktreeInfo(
        name="main",
        branch=main_branch,
        path=".",
        created_at=datetime.min,
        context_mode="fresh",
    )
    main_status = WorktreeStatus(
        info=main_info,
        is_main=True,
        dirty=main_git.is_dirty,
        changed_files=0,
        session_summary=None,
        session_active=False,
    )

    results = [main_status]

    metadata = _load_metadata(project_path)
    for wt in metadata:
        # Skip poisoned metadata rather than resolve an unsafe path.
        try:
            _validate_worktree_name(wt.name)
        except WorktreeError:
            logger.warning("Skipping worktree with unsafe name: %r", wt.name)
            continue

        abs_path = project_path / wt.path
        if not abs_path.exists():
            continue

        # Single porcelain run yields both the dirty flag and the changed-file
        # count (avoids the previous duplicate git status call).
        changed = 0
        result = _run_git(["status", "--porcelain"], abs_path)
        if result and result.returncode == 0 and result.stdout.strip():
            changed = len(result.stdout.strip().split("\n"))

        results.append(
            WorktreeStatus(
                info=wt,
                is_main=False,
                dirty=changed > 0,
                changed_files=changed,
                session_summary=None,
                session_active=False,
            )
        )

    return results
