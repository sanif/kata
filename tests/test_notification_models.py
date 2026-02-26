"""Tests for notification data models."""

import json
from datetime import datetime

from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationStatus,
    NotificationType,
)


class TestNotificationType:
    """Test NotificationType enum."""

    def test_claude_code_types_exist(self):
        assert NotificationType.TASK_COMPLETE.value == "task_complete"
        assert NotificationType.QUESTION.value == "question"
        assert NotificationType.PLAN_READY.value == "plan_ready"
        assert NotificationType.REVIEW_DONE.value == "review_done"
        assert NotificationType.ERROR.value == "error"
        assert NotificationType.SESSION_LIMIT.value == "session_limit"

    def test_kata_types_exist(self):
        assert NotificationType.SESSION_LAUNCHED.value == "session_launched"
        assert NotificationType.SESSION_DETACHED.value == "session_detached"
        assert NotificationType.SESSION_ATTACHED.value == "session_attached"
        assert NotificationType.SESSION_KILLED.value == "session_killed"
        assert NotificationType.ROUTINE_COMPLETE.value == "routine_complete"


class TestNotificationSource:
    """Test NotificationSource enum."""

    def test_sources_exist(self):
        assert NotificationSource.CLAUDE_CODE.value == "claude_code"
        assert NotificationSource.KATA.value == "kata"
        assert NotificationSource.TMUX.value == "tmux"


class TestNotificationStatus:
    """Test NotificationStatus enum."""

    def test_statuses_exist(self):
        assert NotificationStatus.UNREAD.value == "unread"
        assert NotificationStatus.READ.value == "read"
        assert NotificationStatus.DISMISSED.value == "dismissed"


class TestNotification:
    """Test Notification dataclass."""

    def test_create_with_defaults(self):
        n = Notification(
            type=NotificationType.TASK_COMPLETE,
            source=NotificationSource.CLAUDE_CODE,
            title="Task Completed",
        )
        assert n.id  # UUID generated
        assert n.type == NotificationType.TASK_COMPLETE
        assert n.source == NotificationSource.CLAUDE_CODE
        assert n.title == "Task Completed"
        assert n.body == ""
        assert n.session_name == ""
        assert n.priority == 2
        assert n.status == NotificationStatus.UNREAD
        assert n.metadata == {}
        assert isinstance(n.timestamp, datetime)

    def test_create_with_all_fields(self):
        ts = datetime(2026, 2, 26, 12, 0, 0)
        n = Notification(
            type=NotificationType.SESSION_LAUNCHED,
            source=NotificationSource.KATA,
            title="Session launched",
            body="Launched my-project",
            session_name="my-project",
            priority=1,
            status=NotificationStatus.READ,
            metadata={"branch": "main"},
            timestamp=ts,
        )
        assert n.session_name == "my-project"
        assert n.priority == 1
        assert n.status == NotificationStatus.READ
        assert n.metadata == {"branch": "main"}
        assert n.timestamp == ts

    def test_to_dict(self):
        ts = datetime(2026, 2, 26, 12, 0, 0)
        n = Notification(
            id="test-id-123",
            type=NotificationType.TASK_COMPLETE,
            source=NotificationSource.CLAUDE_CODE,
            title="Done",
            body="Finished task",
            session_name="my-proj",
            priority=2,
            metadata={"branch": "feat"},
            timestamp=ts,
        )
        d = n.to_dict()
        assert d["id"] == "test-id-123"
        assert d["type"] == "task_complete"
        assert d["source"] == "claude_code"
        assert d["title"] == "Done"
        assert d["body"] == "Finished task"
        assert d["session_name"] == "my-proj"
        assert d["priority"] == 2
        assert d["status"] == "unread"
        assert d["metadata"] == {"branch": "feat"}
        assert d["timestamp"] == "2026-02-26T12:00:00"
        # Should be JSON-serializable
        json.dumps(d)

    def test_from_dict(self):
        d = {
            "id": "abc-123",
            "type": "task_complete",
            "source": "claude_code",
            "title": "Done",
            "body": "Finished",
            "session_name": "proj",
            "priority": 1,
            "status": "read",
            "metadata": {"x": "y"},
            "timestamp": "2026-02-26T12:00:00",
        }
        n = Notification.from_dict(d)
        assert n.id == "abc-123"
        assert n.type == NotificationType.TASK_COMPLETE
        assert n.source == NotificationSource.CLAUDE_CODE
        assert n.title == "Done"
        assert n.body == "Finished"
        assert n.session_name == "proj"
        assert n.priority == 1
        assert n.status == NotificationStatus.READ
        assert n.metadata == {"x": "y"}
        assert n.timestamp == datetime(2026, 2, 26, 12, 0, 0)

    def test_from_dict_defaults(self):
        d = {
            "id": "abc",
            "type": "question",
            "source": "claude_code",
            "title": "Question",
            "timestamp": "2026-02-26T12:00:00",
        }
        n = Notification.from_dict(d)
        assert n.body == ""
        assert n.session_name == ""
        assert n.priority == 2
        assert n.status == NotificationStatus.UNREAD
        assert n.metadata == {}

    def test_roundtrip(self):
        n = Notification(
            type=NotificationType.ERROR,
            source=NotificationSource.CLAUDE_CODE,
            title="API Error",
            body="Rate limited",
            session_name="proj",
            priority=0,
            metadata={"code": 429},
        )
        d = n.to_dict()
        n2 = Notification.from_dict(d)
        assert n.id == n2.id
        assert n.type == n2.type
        assert n.source == n2.source
        assert n.title == n2.title
        assert n.body == n2.body
        assert n.session_name == n2.session_name
        assert n.priority == n2.priority
        assert n.status == n2.status
        assert n.metadata == n2.metadata

    def test_priority_clamping(self):
        n = Notification(
            type=NotificationType.ERROR,
            source=NotificationSource.CLAUDE_CODE,
            title="Error",
            priority=-1,
        )
        assert n.priority == 0

        n2 = Notification(
            type=NotificationType.ERROR,
            source=NotificationSource.CLAUDE_CODE,
            title="Error",
            priority=5,
        )
        assert n2.priority == 4


class TestNotificationSettings:
    """Test notification settings in global Settings."""

    def test_defaults(self):
        from kata.core.settings import Settings

        s = Settings()
        assert s.notifications_enabled is True
        assert s.notifications_os_enabled is True
        assert s.notifications_sound == "Glass"
        assert s.notifications_retention_days == 7
        assert s.notifications_max_count == 500
        assert s.notifications_claude_code_hooks is True
        assert s.notifications_tmux_hooks is True
        assert s.notifications_suppression_seconds == 5
        assert s.notifications_terminal_app == "auto"

    def test_serialization_roundtrip(self):
        from kata.core.settings import Settings

        s = Settings(notifications_sound="Ping", notifications_max_count=100)
        d = s.to_dict()
        s2 = Settings.from_dict(d)
        assert s2.notifications_sound == "Ping"
        assert s2.notifications_max_count == 100

    def test_retention_days_clamping(self):
        from kata.core.settings import Settings

        s = Settings(notifications_retention_days=0)
        assert s.notifications_retention_days == 1
        s2 = Settings(notifications_retention_days=400)
        assert s2.notifications_retention_days == 365
