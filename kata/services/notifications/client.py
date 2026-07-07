"""Client for communicating with the notification daemon."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from kata.core.config import NOTIFYD_SOCKET
from kata.core.constants import NOTIFY_CLIENT_TIMEOUT, NOTIFY_CONNECT_TIMEOUT
from kata.services.notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationClient:
    """Async client for the notification daemon Unix socket.

    Every network operation is bounded by a timeout so a wedged daemon can
    never block a hook (which would stall an entire agent turn). On timeout the
    caller sees an exception / False and the SQLite fallback path runs.
    """

    def __init__(self) -> None:
        """Initialize the client."""
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        """Connect to the daemon socket (bounded by NOTIFY_CONNECT_TIMEOUT)."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(NOTIFYD_SOCKET)),
            timeout=NOTIFY_CONNECT_TIMEOUT,
        )

    async def close(self) -> None:
        """Close the connection."""
        if self._writer:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=NOTIFY_CLIENT_TIMEOUT)
            except (asyncio.TimeoutError, OSError):
                pass
            self._writer = None
            self._reader = None

    async def _send(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Send a message and read the response (bounded by NOTIFY_CLIENT_TIMEOUT)."""
        if not self._writer or not self._reader:
            raise ConnectionError("Not connected to daemon")

        data = json.dumps(msg) + "\n"
        self._writer.write(data.encode())
        await asyncio.wait_for(self._writer.drain(), timeout=NOTIFY_CLIENT_TIMEOUT)

        response_data = await asyncio.wait_for(
            self._reader.readline(), timeout=NOTIFY_CLIENT_TIMEOUT
        )
        return json.loads(response_data.decode().strip())

    async def send_notification(self, notification: Notification) -> dict[str, Any]:
        """Send a notification to the daemon."""
        return await self._send(
            {
                "action": "notify",
                "notification": notification.to_dict(),
            }
        )

    async def query(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query notifications from the daemon."""
        msg: dict[str, Any] = {"action": "query", "limit": limit}
        if status:
            msg["status"] = status
        result = await self._send(msg)
        return result.get("notifications", [])

    async def update_status(self, notification_id: str, status: str) -> dict[str, Any]:
        """Update a notification's status."""
        return await self._send(
            {
                "action": "update",
                "id": notification_id,
                "status": status,
            }
        )

    async def get_unread_count(self) -> int:
        """Get the unread notification count."""
        result = await self._send({"action": "unread_count"})
        return result.get("count", 0)

    async def mark_all_read(self) -> dict[str, Any]:
        """Mark all notifications as read."""
        return await self._send({"action": "mark_all_read"})

    async def dismiss_all(self) -> dict[str, Any]:
        """Dismiss all notifications."""
        return await self._send({"action": "dismiss_all"})

    async def ping(self) -> bool:
        """Ping the daemon to check if it's alive."""
        try:
            result = await self._send({"action": "ping"})
            return result.get("status") == "pong"
        except Exception:
            return False


def send_notification_sync(notification: Notification) -> bool:
    """Synchronous convenience function for sending a notification.

    Used by hook handlers and Kata services that are not async.
    Returns True if sent successfully, False otherwise.
    """
    try:

        async def _send() -> bool:
            client = NotificationClient()
            try:
                await client.connect()
                result = await client.send_notification(notification)
                return result.get("status") == "ok"
            finally:
                await client.close()

        return asyncio.run(_send())
    except Exception:
        logger.debug("Failed to send notification to daemon", exc_info=True)
        return False
