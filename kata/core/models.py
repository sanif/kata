"""Core data models for Kata."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SessionStatus(Enum):
    """Status of a tmux session."""

    IDLE = "idle"  # No tmux session exists
    ACTIVE = "active"  # Session running, client attached
    DETACHED = "detached"  # Session running, no client


class ProjectType(Enum):
    """Detected project type based on markers."""

    PYTHON = "python"
    NODE = "node"
    GO = "go"
    GENERIC = "generic"


@dataclass
class Project:
    """Represents a registered project in Kata."""

    name: str  # Unique identifier, derived from directory name
    path: str  # Absolute path to project root
    group: str = "Uncategorized"  # Grouping category
    config: str = ""  # Relative path to YAML config (project-name.yaml)
    created_at: datetime = field(default_factory=datetime.now)
    last_opened: datetime | None = None
    times_opened: int = 0
    shortcut: int | None = None  # Quick launch shortcut (1-9)
    color: str | None = None  # Display color (preset name or hex)
    # NOTE: `config` is currently write-only — set here and by the TUI rename
    # flow, but never read to locate a config (launch uses the project's
    # .kata.yaml via core.config). Left in place because context_menu.py still
    # writes it; a candidate for removal in the TUI cleanup batch.

    def __post_init__(self) -> None:
        """Normalize the path and default the config filename.

        A non-empty path is resolved to an absolute path. An empty path is
        preserved as-is: some transient placeholders (e.g. "project not found"
        results) carry no path, and resolving "" would silently point at the
        current working directory.
        """
        if self.path:
            self.path = str(Path(self.path).resolve())
        if not self.config:
            self.config = f"{self.name}.yaml"

    def to_dict(self) -> dict[str, Any]:
        """Serialize project to dictionary for JSON storage."""
        return {
            "name": self.name,
            "path": self.path,
            "group": self.group,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "last_opened": self.last_opened.isoformat() if self.last_opened else None,
            "times_opened": self.times_opened,
            "shortcut": self.shortcut,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """Deserialize project from dictionary."""
        return cls(
            name=data["name"],
            path=data["path"],
            group=data.get("group", "Uncategorized"),
            config=data.get("config", f"{data['name']}.yaml"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_opened=(
                datetime.fromisoformat(data["last_opened"]) if data.get("last_opened") else None
            ),
            times_opened=data.get("times_opened", 0),
            shortcut=data.get("shortcut"),
            color=data.get("color"),
        )

    @classmethod
    def from_path(cls, path: str | Path, group: str = "Uncategorized") -> "Project":
        """Create a project from a directory path."""
        path_obj = Path(path).resolve()
        name = path_obj.name
        return cls(name=name, path=str(path_obj), group=group)

    def record_open(self) -> None:
        """Record that the project was opened."""
        self.last_opened = datetime.now()
        self.times_opened += 1


@dataclass
class WorktreeInfo:
    """Metadata for a git worktree managed by kata."""

    name: str
    branch: str
    path: str  # relative to project root
    created_at: datetime
    context_mode: str  # "fork" | "summary" | "fresh"
    source_session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "branch": self.branch,
            "path": self.path,
            "created_at": self.created_at.isoformat(),
            "context_mode": self.context_mode,
            "source_session_id": self.source_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorktreeInfo":
        return cls(
            name=data["name"],
            branch=data["branch"],
            path=data["path"],
            created_at=datetime.fromisoformat(data["created_at"]),
            context_mode=data.get("context_mode", "fresh"),
            source_session_id=data.get("source_session_id"),
        )


@dataclass
class WorktreeStatus:
    """Runtime status of a worktree including git and session state."""

    info: WorktreeInfo
    is_main: bool
    dirty: bool
    changed_files: int
    session_summary: str | None
    session_active: bool
