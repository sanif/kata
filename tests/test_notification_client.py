"""Tests for notification client."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from kata.services.notifications.client import NotificationClient
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
