"""Tests for notification daemon."""

import json
import tempfile
from pathlib import Path

import pytest

from kata.services.notifications.daemon import NotificationDaemon
from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationType,
)


@pytest.fixture
def temp_paths():
    """Create temporary paths for socket, pid, and db."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yield {
            "socket": tmpdir_path / "test.sock",
            "pid": tmpdir_path / "test.pid",
            "db": tmpdir_path / "test.db",
        }


@pytest.fixture
def daemon(temp_paths):
    """Create a daemon with temporary paths."""
    d = NotificationDaemon(db_path=temp_paths["db"])
    yield d
    d.store.close()


def _make_notification(**kwargs) -> dict:
    """Helper to create a notification dict."""
    n = Notification(
        type=NotificationType.TASK_COMPLETE,
        source=NotificationSource.CLAUDE_CODE,
        title=kwargs.get("title", "Test"),
        body=kwargs.get("body", ""),
        session_name=kwargs.get("session_name", ""),
    )
    return n.to_dict()


class TestNotificationDaemon:
    """Test the notification daemon."""

    def test_daemon_creates(self, daemon):
        """Daemon should instantiate without error."""
        assert daemon is not None

    @pytest.mark.asyncio
    async def test_handle_notify_action(self, daemon):
        """Test handling a notify action."""
        msg = {
            "action": "notify",
            "notification": _make_notification(title="Hello"),
        }
        response = await daemon.handle_message(json.dumps(msg))
        parsed = json.loads(response)
        assert parsed["status"] == "ok"

        # Verify it was stored
        count = daemon.store.unread_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_handle_query_action(self, daemon):
        """Test handling a query action."""
        # Add some notifications
        for i in range(3):
            msg = {
                "action": "notify",
                "notification": _make_notification(title=f"N{i}"),
            }
            await daemon.handle_message(json.dumps(msg))

        # Query
        query_msg = json.dumps({"action": "query", "status": "unread"})
        response = await daemon.handle_message(query_msg)
        parsed = json.loads(response)
        assert parsed["event"] == "query_result"
        assert len(parsed["notifications"]) == 3

    @pytest.mark.asyncio
    async def test_handle_update_action(self, daemon):
        """Test handling an update action."""
        # Add a notification
        n = _make_notification(title="To update")
        msg = json.dumps({"action": "notify", "notification": n})
        await daemon.handle_message(msg)

        # Update it
        update_msg = json.dumps(
            {
                "action": "update",
                "id": n["id"],
                "status": "read",
            }
        )
        response = await daemon.handle_message(update_msg)
        parsed = json.loads(response)
        assert parsed["status"] == "ok"

        # Verify
        stored = daemon.store.get(n["id"])
        assert stored is not None
        assert stored.status.value == "read"

    @pytest.mark.asyncio
    async def test_handle_ping_action(self, daemon):
        """Test handling a ping action."""
        msg = json.dumps({"action": "ping"})
        response = await daemon.handle_message(msg)
        parsed = json.loads(response)
        assert parsed["status"] == "pong"

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self, daemon):
        """Test handling unknown action."""
        msg = json.dumps({"action": "unknown"})
        response = await daemon.handle_message(msg)
        parsed = json.loads(response)
        assert parsed["status"] == "error"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, daemon):
        """Test handling invalid JSON."""
        response = await daemon.handle_message("not json{{{")
        parsed = json.loads(response)
        assert parsed["status"] == "error"
