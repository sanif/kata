"""SQLite-backed notification store."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from kata.core.config import NOTIFICATIONS_DB, ensure_config_dirs
from kata.core.constants import DB_BUSY_TIMEOUT_MS, DB_CONNECT_TIMEOUT
from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationStatus,
    NotificationType,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    session_name TEXT DEFAULT '',
    priority INTEGER DEFAULT 2,
    status TEXT DEFAULT 'unread',
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_source ON notifications(source);
"""


class NotificationStore:
    """SQLite-backed store for notifications."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the store and create schema if needed."""
        self._db_path = db_path or NOTIFICATIONS_DB
        if db_path is None:
            ensure_config_dirs()
        self._conn = sqlite3.connect(
            str(self._db_path), timeout=DB_CONNECT_TIMEOUT, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # DB locked by another process, WAL will be set on next open
        # Only create schema if table doesn't exist (avoids write lock)
        tables = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
        ).fetchone()
        if not tables:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def add(self, notification: Notification) -> None:
        """Add a notification to the store."""
        d = notification.to_dict()
        self._conn.execute(
            """INSERT INTO notifications
               (id, timestamp, type, source, title, body, session_name,
                priority, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d["id"],
                d["timestamp"],
                d["type"],
                d["source"],
                d["title"],
                d["body"],
                d["session_name"],
                d["priority"],
                d["status"],
                json.dumps(d["metadata"]),
            ),
        )
        self._conn.commit()

    def get(self, notification_id: str) -> Notification | None:
        """Get a notification by ID."""
        row = self._conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_notification(row)

    def list_all(self, limit: int = 0) -> list[Notification]:
        """List all notifications, ordered by timestamp descending."""
        if limit > 0:
            rows = self._conn.execute(
                "SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM notifications ORDER BY timestamp DESC"
            ).fetchall()
        return [self._row_to_notification(r) for r in rows]

    def list_by_status(self, status: NotificationStatus) -> list[Notification]:
        """List notifications filtered by status."""
        rows = self._conn.execute(
            "SELECT * FROM notifications WHERE status = ? ORDER BY timestamp DESC",
            (status.value,),
        ).fetchall()
        return [self._row_to_notification(r) for r in rows]

    def list_by_source(self, source: NotificationSource) -> list[Notification]:
        """List notifications filtered by source."""
        rows = self._conn.execute(
            "SELECT * FROM notifications WHERE source = ? ORDER BY timestamp DESC",
            (source.value,),
        ).fetchall()
        return [self._row_to_notification(r) for r in rows]

    def list_grouped_by_session(self) -> dict[str, list[Notification]]:
        """Group non-dismissed notifications by session_name.

        Returns an ordered dict: keys are session names sorted by most-recent
        notification timestamp (newest first). Entries with empty session_name
        are excluded.
        """
        rows = self._conn.execute(
            """SELECT * FROM notifications
               WHERE status != ? AND session_name != ''
               ORDER BY timestamp DESC""",
            (NotificationStatus.DISMISSED.value,),
        ).fetchall()

        groups: dict[str, list[Notification]] = {}
        for row in rows:
            n = self._row_to_notification(row)
            groups.setdefault(n.session_name, []).append(n)
        return groups

    def dismiss_by_session(self, session_name: str) -> None:
        """Dismiss all notifications for a session."""
        self._conn.execute(
            "UPDATE notifications SET status = ? WHERE session_name = ? AND status != ?",
            (NotificationStatus.DISMISSED.value, session_name, NotificationStatus.DISMISSED.value),
        )
        self._conn.commit()

    def mark_session_read(self, session_name: str) -> None:
        """Mark all notifications for a session as read."""
        self._conn.execute(
            "UPDATE notifications SET status = ? WHERE session_name = ? AND status = ?",
            (NotificationStatus.READ.value, session_name, NotificationStatus.UNREAD.value),
        )
        self._conn.commit()

    def update_status(self, notification_id: str, status: NotificationStatus) -> None:
        """Update a notification's status."""
        self._conn.execute(
            "UPDATE notifications SET status = ? WHERE id = ?",
            (status.value, notification_id),
        )
        self._conn.commit()

    def mark_all_read(self) -> None:
        """Mark all unread notifications as read."""
        self._conn.execute(
            "UPDATE notifications SET status = ? WHERE status = ?",
            (NotificationStatus.READ.value, NotificationStatus.UNREAD.value),
        )
        self._conn.commit()

    def dismiss(self, notification_id: str) -> None:
        """Dismiss a notification."""
        self.update_status(notification_id, NotificationStatus.DISMISSED)

    def dismiss_all(self) -> None:
        """Dismiss all notifications."""
        self._conn.execute(
            "UPDATE notifications SET status = ?",
            (NotificationStatus.DISMISSED.value,),
        )
        self._conn.commit()

    def delete(self, notification_id: str) -> None:
        """Delete a notification permanently."""
        self._conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
        self._conn.commit()

    def unread_count(self) -> int:
        """Count unread notifications."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE status = ?",
            (NotificationStatus.UNREAD.value,),
        ).fetchone()
        return row[0] if row else 0

    def prune(
        self,
        max_age_days: int = 7,
        max_count: int = 500,
    ) -> int:
        """Remove old notifications. Returns count of removed entries."""
        removed = 0

        # Prune by age
        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        cursor = self._conn.execute("DELETE FROM notifications WHERE timestamp < ?", (cutoff,))
        removed += cursor.rowcount

        # Prune by count (keep most recent max_count)
        cursor = self._conn.execute(
            """DELETE FROM notifications WHERE id NOT IN (
                SELECT id FROM notifications ORDER BY timestamp DESC LIMIT ?
            )""",
            (max_count,),
        )
        removed += cursor.rowcount

        if removed > 0:
            self._conn.commit()

        return removed

    def _row_to_notification(self, row: Any) -> Notification:
        """Convert a database row to a Notification object."""
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return Notification(
            id=row["id"],
            type=NotificationType(row["type"]),
            source=NotificationSource(row["source"]),
            title=row["title"],
            body=row["body"],
            session_name=row["session_name"],
            priority=row["priority"],
            status=NotificationStatus(row["status"]),
            metadata=metadata,
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )


# Singleton
_store: NotificationStore | None = None


def get_notification_store() -> NotificationStore:
    """Get the notification store singleton."""
    global _store
    if _store is None:
        _store = NotificationStore()
    return _store
