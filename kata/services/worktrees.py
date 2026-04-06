"""Service for managing git worktrees within kata projects."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import WorktreeInfo, WorktreeStatus
from kata.utils.git import get_branch_name, get_git_status

WORKTREES_DIR = ".worktrees"
METADATA_FILE = ".kata-worktrees.json"


class WorktreeError(Exception):
    """Raised when a worktree operation fails."""


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
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


def _metadata_path(project_path: Path) -> Path:
    return project_path / WORKTREES_DIR / METADATA_FILE


def _load_metadata(project_path: Path) -> list[WorktreeInfo]:
    path = _metadata_path(project_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [WorktreeInfo.from_dict(w) for w in data.get("worktrees", [])]
    except (json.JSONDecodeError, KeyError, ValueError):
        return []


def _save_metadata(project_path: Path, worktrees: list[WorktreeInfo]) -> None:
    path = _metadata_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"worktrees": [w.to_dict() for w in worktrees]}
    path.write_text(json.dumps(data, indent=2) + "\n")


def _ensure_gitignore(project_path: Path) -> None:
    gitignore = project_path / ".gitignore"
    entry = ".worktrees/"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{entry}\n"
        gitignore.write_text(content)
    else:
        gitignore.write_text(f"{entry}\n")


def _symlink_shared_files(project_path: Path, wt_path: Path) -> None:
    shared = [".env", "node_modules", ".venv"]
    for name in shared:
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


def delete_worktree(project_path: Path | str, name: str, force: bool = False) -> None:
    project_path = Path(project_path).resolve()
    if name == "main":
        raise WorktreeError("Cannot delete main worktree")

    existing = _load_metadata(project_path)
    wt = next((w for w in existing if w.name == name), None)
    if wt is None:
        raise WorktreeError(f"Worktree '{name}' not found")

    abs_wt_path = project_path / wt.path

    # Clean up kata-generated files that would block git worktree remove
    _cleanup_worktree_files(abs_wt_path)

    # Kill any tmux session using this worktree
    _kill_worktree_session(abs_wt_path)

    args = ["worktree", "remove", str(abs_wt_path)]
    if force:
        args.append("--force")
    result = _run_git(args, project_path)

    # If safe remove fails due to untracked files, retry with --force
    if result and result.returncode != 0 and not force:
        if "untracked" in (result.stderr or "") or "modified" in (result.stderr or ""):
            args.append("--force")
            result = _run_git(args, project_path)

    if result is None or result.returncode != 0:
        stderr = result.stderr if result else "git command failed"
        raise WorktreeError(f"Failed to remove worktree: {stderr}")

    branch_args = ["-D" if force else "-d", wt.branch]
    _run_git(["branch"] + branch_args, project_path)

    existing = [w for w in existing if w.name != name]
    _save_metadata(project_path, existing)


def _cleanup_worktree_files(wt_path: Path) -> None:
    """Remove kata-generated files from a worktree before deletion."""
    import shutil

    # Remove .claude/ dir we created for context seeding
    claude_dir = wt_path / ".claude"
    if claude_dir.exists():
        shutil.rmtree(claude_dir, ignore_errors=True)

    # Remove symlinks we created
    for name in [".kata.yaml", ".env", "node_modules", ".venv"]:
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
            session_name, session_path = line.split("|", 1)
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
        dirty=main_git.is_dirty if hasattr(main_git, "is_dirty") else False,
        changed_files=0,
        session_summary=None,
        session_active=False,
    )

    results = [main_status]

    metadata = _load_metadata(project_path)
    for wt in metadata:
        abs_path = project_path / wt.path
        if not abs_path.exists():
            continue

        git_status = get_git_status(abs_path)
        changed = 0
        result = _run_git(["status", "--porcelain"], abs_path)
        if result and result.returncode == 0 and result.stdout.strip():
            changed = len(result.stdout.strip().split("\n"))

        results.append(
            WorktreeStatus(
                info=wt,
                is_main=False,
                dirty=git_status.is_dirty,
                changed_files=changed,
                session_summary=None,
                session_active=False,
            )
        )

    return results
