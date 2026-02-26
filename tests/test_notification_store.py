"""Tests for notification SQLite store."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationStatus,
    NotificationType,
)
from kata.services.notifications.store import NotificationStore


@staticmethod
def _temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


def _make_notification(**kwargs) -> Notification:
    """Helper to create a test notification."""
    defaults = {
        "type": NotificationType.TASK_COMPLETE,
        "source": NotificationSource.CLAUDE_CODE,
        "title": "Test notification",
    }
    defaults.update(kwargs)
    return Notification(**defaults)


class TestNotificationStore:
    """Test cases for NotificationStore."""

    def _make_store(self):
        """Create a store with a temp database."""
        temp_path = _temp_db()
        store = NotificationStore(db_path=temp_path)
        return store, temp_path

    def test_add_and_get(self):
        store, temp_path = self._make_store()
        try:
            n = _make_notification(title="Test add")
            store.add(n)
            retrieved = store.get(n.id)
            assert retrieved is not None
            assert retrieved.id == n.id
            assert retrieved.title == "Test add"
            assert retrieved.type == NotificationType.TASK_COMPLETE
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_get_nonexistent_returns_none(self):
        store, temp_path = self._make_store()
        try:
            assert store.get("nonexistent-id") is None
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_list_all(self):
        store, temp_path = self._make_store()
        try:
            for i in range(3):
                store.add(_make_notification(title=f"N{i}"))
            notifications = store.list_all()
            assert len(notifications) == 3
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_list_all_ordered_by_timestamp_desc(self):
        store, temp_path = self._make_store()
        try:
            old = _make_notification(
                title="Old",
                timestamp=datetime(2026, 1, 1),
            )
            new = _make_notification(
                title="New",
                timestamp=datetime(2026, 2, 26),
            )
            store.add(old)
            store.add(new)
            notifications = store.list_all()
            assert notifications[0].title == "New"
            assert notifications[1].title == "Old"
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_list_by_status(self):
        store, temp_path = self._make_store()
        try:
            store.add(_make_notification(title="Unread1"))
            n2 = _make_notification(title="Read1", status=NotificationStatus.READ)
            store.add(n2)
            store.add(_make_notification(title="Unread2"))

            unread = store.list_by_status(NotificationStatus.UNREAD)
            assert len(unread) == 2
            read = store.list_by_status(NotificationStatus.READ)
            assert len(read) == 1
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_list_by_source(self):
        store, temp_path = self._make_store()
        try:
            store.add(_make_notification(title="CC", source=NotificationSource.CLAUDE_CODE))
            store.add(_make_notification(title="Kata", source=NotificationSource.KATA))
            cc = store.list_by_source(NotificationSource.CLAUDE_CODE)
            assert len(cc) == 1
            assert cc[0].title == "CC"
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_update_status(self):
        store, temp_path = self._make_store()
        try:
            n = _make_notification(title="To read")
            store.add(n)
            store.update_status(n.id, NotificationStatus.READ)
            retrieved = store.get(n.id)
            assert retrieved is not None
            assert retrieved.status == NotificationStatus.READ
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_update_status_nonexistent(self):
        store, temp_path = self._make_store()
        try:
            # Should not raise, just no-op
            store.update_status("nonexistent", NotificationStatus.READ)
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_mark_all_read(self):
        store, temp_path = self._make_store()
        try:
            for i in range(3):
                store.add(_make_notification(title=f"N{i}"))
            store.mark_all_read()
            unread = store.list_by_status(NotificationStatus.UNREAD)
            assert len(unread) == 0
            read = store.list_by_status(NotificationStatus.READ)
            assert len(read) == 3
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_dismiss(self):
        store, temp_path = self._make_store()
        try:
            n = _make_notification(title="To dismiss")
            store.add(n)
            store.dismiss(n.id)
            retrieved = store.get(n.id)
            assert retrieved is not None
            assert retrieved.status == NotificationStatus.DISMISSED
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_dismiss_all(self):
        store, temp_path = self._make_store()
        try:
            for i in range(3):
                store.add(_make_notification(title=f"N{i}"))
            store.dismiss_all()
            all_notifs = store.list_all()
            assert all(n.status == NotificationStatus.DISMISSED for n in all_notifs)
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_delete(self):
        store, temp_path = self._make_store()
        try:
            n = _make_notification(title="To delete")
            store.add(n)
            store.delete(n.id)
            assert store.get(n.id) is None
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_unread_count(self):
        store, temp_path = self._make_store()
        try:
            store.add(_make_notification(title="U1"))
            store.add(_make_notification(title="U2"))
            store.add(_make_notification(title="R1", status=NotificationStatus.READ))
            assert store.unread_count() == 2
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_prune_by_age(self):
        store, temp_path = self._make_store()
        try:
            old = _make_notification(
                title="Old",
                timestamp=datetime.now() - timedelta(days=10),
            )
            recent = _make_notification(
                title="Recent",
                timestamp=datetime.now(),
            )
            store.add(old)
            store.add(recent)
            store.prune(max_age_days=7)
            all_notifs = store.list_all()
            assert len(all_notifs) == 1
            assert all_notifs[0].title == "Recent"
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_prune_by_count(self):
        store, temp_path = self._make_store()
        try:
            for i in range(10):
                store.add(
                    _make_notification(
                        title=f"N{i}",
                        timestamp=datetime.now() - timedelta(minutes=10 - i),
                    )
                )
            store.prune(max_count=5)
            all_notifs = store.list_all()
            assert len(all_notifs) == 5
            # Should keep the 5 most recent
            titles = [n.title for n in all_notifs]
            assert "N9" in titles
            assert "N5" in titles
            assert "N0" not in titles
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)

    def test_list_with_limit(self):
        store, temp_path = self._make_store()
        try:
            for i in range(10):
                store.add(_make_notification(title=f"N{i}"))
            limited = store.list_all(limit=3)
            assert len(limited) == 3
        finally:
            store.close()
            temp_path.unlink(missing_ok=True)
