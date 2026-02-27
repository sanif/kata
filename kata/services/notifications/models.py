"""Data models for the notification system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NotificationType(Enum):
    """Types of notifications."""

    # Claude Code events
    TASK_COMPLETE = "task_complete"
    QUESTION = "question"
    PLAN_READY = "plan_ready"
    REVIEW_DONE = "review_done"
    ERROR = "error"
    SESSION_LIMIT = "session_limit"

    # Kata events
    ROUTINE_COMPLETE = "routine_complete"


class NotificationSource(Enum):
    """Source of a notification."""

    CLAUDE_CODE = "claude_code"
    KATA = "kata"
    TMUX = "tmux"


class NotificationStatus(Enum):
    """Status of a notification."""

    UNREAD = "unread"
    READ = "read"
    DISMISSED = "dismissed"


@dataclass
class Notification:
    """A notification event from any source."""

    type: NotificationType
    source: NotificationSource
    title: str
    body: str = ""
    session_name: str = ""
    priority: int = 2  # 0=critical, 1=high, 2=normal, 3=low, 4=backlog
    status: NotificationStatus = NotificationStatus.UNREAD
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Validate and clamp values."""
        self.priority = max(0, min(4, self.priority))

    def to_dict(self) -> dict[str, Any]:
        """Serialize notification to dictionary for JSON/SQLite storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source.value,
            "title": self.title,
            "body": self.body,
            "session_name": self.session_name,
            "priority": self.priority,
            "status": self.status.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Notification:
        """Deserialize notification from dictionary."""
        return cls(
            id=data["id"],
            type=NotificationType(data["type"]),
            source=NotificationSource(data["source"]),
            title=data["title"],
            body=data.get("body", ""),
            session_name=data.get("session_name", ""),
            priority=data.get("priority", 2),
            status=NotificationStatus(data.get("status", "unread")),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
