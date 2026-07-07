"""Tests for notification client."""

import asyncio
import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

import kata.services.notifications.client as client_mod
from kata.services.notifications.client import NotificationClient, send_notification_sync
from kata.services.notifications.daemon import NotificationDaemon
from kata.services.notifications.models import (
    Notification,
    NotificationSource,
    NotificationType,
)


@pytest.fixture
def temp_paths():
    """Create temporary paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yield {
            "socket": tmpdir_path / "test.sock",
            "pid": tmpdir_path / "test.pid",
            "db": tmpdir_path / "test.db",
        }


@pytest.mark.asyncio
async def test_client_send_notification(temp_paths):
    """Test sending a notification through the client to the daemon."""
    daemon = NotificationDaemon(db_path=temp_paths["db"])

    # Start daemon in background
    server = await asyncio.start_unix_server(daemon._handle_client, path=str(temp_paths["socket"]))

    try:
        async with server:
            with patch("kata.services.notifications.client.NOTIFYD_SOCKET", temp_paths["socket"]):
                client = NotificationClient()
                await client.connect()

                n = Notification(
                    type=NotificationType.TASK_COMPLETE,
                    source=NotificationSource.CLAUDE_CODE,
                    title="Test via client",
                )
                result = await client.send_notification(n)
                assert result["status"] == "ok"

                # Verify stored
                assert daemon.store.unread_count() == 1

                await client.close()
    finally:
        server.close()
        daemon.store.close()


@pytest.mark.asyncio
async def test_client_query(temp_paths):
    """Test querying notifications through the client."""
    daemon = NotificationDaemon(db_path=temp_paths["db"])

    server = await asyncio.start_unix_server(daemon._handle_client, path=str(temp_paths["socket"]))

    try:
        async with server:
            # Add directly to store
            n = Notification(
                type=NotificationType.TASK_COMPLETE,
                source=NotificationSource.CLAUDE_CODE,
                title="Pre-existing",
            )
            daemon.store.add(n)

            with patch("kata.services.notifications.client.NOTIFYD_SOCKET", temp_paths["socket"]):
                client = NotificationClient()
                await client.connect()

                result = await client.query()
                assert len(result) == 1
                assert result[0]["title"] == "Pre-existing"

                await client.close()
    finally:
        server.close()
        daemon.store.close()


@pytest.mark.asyncio
async def test_client_ping(temp_paths):
    """Test pinging the daemon."""
    daemon = NotificationDaemon(db_path=temp_paths["db"])

    server = await asyncio.start_unix_server(daemon._handle_client, path=str(temp_paths["socket"]))

    try:
        async with server:
            with patch("kata.services.notifications.client.NOTIFYD_SOCKET", temp_paths["socket"]):
                client = NotificationClient()
                await client.connect()
                assert await client.ping() is True
                await client.close()
    finally:
        server.close()
        daemon.store.close()


def test_send_notification_sync_times_out_on_hung_server(temp_paths, monkeypatch):
    """A daemon that accepts the connection but never replies must not hang the
    hook: send_notification_sync returns False so the SQLite fallback runs."""
    sock_path = temp_paths["socket"]
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)
    srv.settimeout(0.5)

    conns: list[socket.socket] = []
    stop = threading.Event()

    def accept_loop() -> None:
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
                conns.append(conn)  # accept, then deliberately never reply
            except TimeoutError:
                continue
            except OSError:
                break

    t = threading.Thread(target=accept_loop, daemon=True)
    t.start()

    try:
        monkeypatch.setattr(client_mod, "NOTIFYD_SOCKET", sock_path)
        monkeypatch.setattr(client_mod, "NOTIFY_CLIENT_TIMEOUT", 0.3)

        notification = Notification(
            type=NotificationType.TASK_COMPLETE,
            source=NotificationSource.CLAUDE_CODE,
            title="hung",
        )
        result = send_notification_sync(notification)
        assert result is False
    finally:
        stop.set()
        srv.close()
        for c in conns:
            c.close()
        t.join(timeout=2)
