"""Client for communicating with the notification daemon."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from kata.core.config import NOTIFYD_SOCKET
from kata.services.notifications.models import Notification

logger = logging.getLogger(__name__)


class NotificationClient:
    """Async client for the notification daemon Unix socket."""

    def __init__(self) -> None:
        """Initialize the client."""
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        """Connect to the daemon socket."""
        self._reader, self._writer = await asyncio.open_unix_connection(str(NOTIFYD_SOCKET))

    async def close(self) -> None:
        """Close the connection."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def _send(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Send a message and read the response."""
        if not self._writer or not self._reader:
            raise ConnectionError("Not connected to daemon")

        data = json.dumps(msg) + "\n"
        self._writer.write(data.encode())
        await self._writer.drain()

        response_data = await self._reader.readline()
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

    async def subscribe(self) -> None:
        """Subscribe to real-time notification events.

        After calling this, use `read_event()` to receive pushed events.
        """
        await self._send({"action": "subscribe"})

    async def read_event(self) -> dict[str, Any] | None:
        """Read the next pushed event from a subscription."""
        if not self._reader:
            return None
        try:
            data = await self._reader.readline()
            if not data:
                return None
            return json.loads(data.decode().strip())
        except Exception:
            return None


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
