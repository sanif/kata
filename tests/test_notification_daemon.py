"""Tests for notification daemon."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from kata.services.notifications import daemon as daemon_mod
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

    @pytest.mark.asyncio
    async def test_handle_non_object_payload(self, daemon):
        """A JSON array/number must be rejected, not crash."""
        response = await daemon.handle_message("[1, 2, 3]")
        parsed = json.loads(response)
        assert parsed["status"] == "error"

    @pytest.mark.asyncio
    async def test_handle_query_rejects_bad_limit(self, daemon):
        """A typed-but-malformed limit must produce an error, not kill anything."""
        response = await daemon.handle_message(
            json.dumps({"action": "query", "limit": "not-a-number"})
        )
        parsed = json.loads(response)
        assert parsed["status"] == "error"

    @pytest.mark.asyncio
    async def test_handle_query_string_limit_coerced(self, daemon):
        """A numeric-string limit is coerced rather than rejected."""
        response = await daemon.handle_message(json.dumps({"action": "query", "limit": "5"}))
        parsed = json.loads(response)
        assert parsed["event"] == "query_result"

    @pytest.mark.asyncio
    async def test_handle_notify_missing_notification(self, daemon):
        """A notify action without a notification object errors cleanly."""
        response = await daemon.handle_message(json.dumps({"action": "notify"}))
        parsed = json.loads(response)
        assert parsed["status"] == "error"

    @pytest.mark.asyncio
    async def test_handle_update_bad_types(self, daemon):
        """Non-string id/status must error, not raise."""
        response = await daemon.handle_message(
            json.dumps({"action": "update", "id": 123, "status": ["read"]})
        )
        parsed = json.loads(response)
        assert parsed["status"] == "error"


async def _async_ping(sock_path) -> bool:
    """Ping the daemon without blocking the event loop (unlike sync _ping_socket)."""
    reader, writer = await asyncio.open_unix_connection(str(sock_path))
    writer.write(b'{"action": "ping"}\n')
    await writer.drain()
    data = await asyncio.wait_for(reader.readline(), timeout=1.0)
    writer.close()
    return b"pong" in data


class TestDaemonLifecycle:
    """Exercise start()/stop(), the double-start guard, and file ownership."""

    @pytest.mark.asyncio
    async def test_start_creates_files_and_stop_cleans(self, monkeypatch, temp_paths):
        monkeypatch.setattr(daemon_mod, "NOTIFYD_SOCKET", temp_paths["socket"])
        monkeypatch.setattr(daemon_mod, "NOTIFYD_PID_FILE", temp_paths["pid"])
        monkeypatch.setattr(daemon_mod, "ensure_config_dirs", lambda: None)

        d = NotificationDaemon(db_path=temp_paths["db"])
        task = asyncio.ensure_future(d.start())

        # Wait for the daemon to come up (async ping so we don't block the loop).
        alive = False
        for _ in range(60):
            if temp_paths["socket"].exists():
                try:
                    alive = await _async_ping(temp_paths["socket"])
                    if alive:
                        break
                except (ConnectionRefusedError, FileNotFoundError, OSError):
                    pass
            await asyncio.sleep(0.05)

        try:
            assert alive is True
            assert temp_paths["socket"].exists()
            assert temp_paths["pid"].read_text().strip() == str(os.getpid())
        finally:
            d.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # stop() cleaned up files it owned.
        assert not temp_paths["pid"].exists()

    @pytest.mark.asyncio
    async def test_double_start_refused(self, monkeypatch, temp_paths):
        # Simulate a live daemon already answering the socket.
        temp_paths["socket"].touch()
        monkeypatch.setattr(daemon_mod, "NOTIFYD_SOCKET", temp_paths["socket"])
        monkeypatch.setattr(daemon_mod, "NOTIFYD_PID_FILE", temp_paths["pid"])
        monkeypatch.setattr(daemon_mod, "ensure_config_dirs", lambda: None)
        monkeypatch.setattr(daemon_mod, "_ping_socket", lambda: True)

        d = NotificationDaemon(db_path=temp_paths["db"])
        try:
            with pytest.raises(daemon_mod.DaemonAlreadyRunning):
                await d.start()
            # The existing socket must NOT have been unlinked.
            assert temp_paths["socket"].exists()
        finally:
            d.store.close()

    @pytest.mark.asyncio
    async def test_oversized_line_returns_error(self, temp_paths):
        """A line exceeding the stream limit must yield an error, not crash."""
        daemon = NotificationDaemon(db_path=temp_paths["db"])

        # A small-limit reader whose buffer exceeds the limit with no newline
        # makes readline() raise LimitOverrunError/ValueError.
        reader = asyncio.StreamReader(limit=64)
        reader.feed_data(b"x" * 400)  # no newline, exceeds the 64-byte limit

        written: list[bytes] = []

        class FakeWriter:
            def write(self, data: bytes) -> None:
                written.append(data)

            async def drain(self) -> None:
                pass

            def close(self) -> None:
                pass

        try:
            await asyncio.wait_for(daemon._handle_client(reader, FakeWriter()), timeout=2.0)
            assert any(b"error" in chunk for chunk in written)
        finally:
            daemon.store.close()


def test_is_daemon_running_cleans_stale_pid(monkeypatch, tmp_path):
    pid_file = tmp_path / "pid"
    sock = tmp_path / "sock"
    monkeypatch.setattr(daemon_mod, "NOTIFYD_PID_FILE", pid_file)
    monkeypatch.setattr(daemon_mod, "NOTIFYD_SOCKET", sock)
    pid_file.write_text("999999")  # a PID that almost certainly doesn't exist

    assert daemon_mod.is_daemon_running() is False
    assert not pid_file.exists()  # stale PID file removed


def test_spawn_detached_uses_new_session(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon_mod, "KATA_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(daemon_mod, "ensure_config_dirs", lambda: None)

    captured = {}

    class FakeProc:
        pid = 4321

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", fake_popen)

    pid = daemon_mod.spawn_detached()

    assert pid == 4321
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["cmd"] == [
        sys.executable,
        "-m",
        "kata.services.notifications.daemon",
    ]
