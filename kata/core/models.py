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

    def __post_init__(self) -> None:
        """Ensure path is absolute and config is set."""
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
