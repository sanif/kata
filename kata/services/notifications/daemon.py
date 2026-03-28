"""Notification daemon — asyncio Unix socket server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from kata.core.config import NOTIFYD_PID_FILE, NOTIFYD_SOCKET, ensure_config_dirs
from kata.services.notifications.models import Notification, NotificationStatus
from kata.services.notifications.store import NotificationStore

logger = logging.getLogger(__name__)


class NotificationDaemon:
    """Background daemon that manages notifications via Unix socket."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the daemon."""
        self.store = NotificationStore(db_path=db_path)
        self._subscribers: list[asyncio.StreamWriter] = []
        self._server: asyncio.AbstractServer | None = None

    async def handle_message(self, raw: str) -> str:
        """Handle a single message and return a response."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

        action = msg.get("action")

        if action == "ping":
            return json.dumps({"status": "pong"})

        elif action == "notify":
            return await self._handle_notify(msg)

        elif action == "subscribe":
            # Subscribe is handled at the connection level, not here
            return json.dumps({"status": "ok", "message": "subscribed"})

        elif action == "query":
            return self._handle_query(msg)

        elif action == "update":
            return self._handle_update(msg)

        elif action == "unread_count":
            count = self.store.unread_count()
            return json.dumps({"event": "unread_count", "count": count})

        elif action == "mark_all_read":
            self.store.mark_all_read()
            return json.dumps({"status": "ok"})

        elif action == "dismiss_all":
            self.store.dismiss_all()
            return json.dumps({"status": "ok"})

        else:
            return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

    async def _handle_notify(self, msg: dict[str, Any]) -> str:
        """Handle a notify action — store and broadcast."""
        try:
            notification_data = msg["notification"]
            notification = Notification.from_dict(notification_data)
            self.store.add(notification)

            # Broadcast to subscribers
            event = json.dumps(
                {
                    "event": "new_notification",
                    "notification": notification.to_dict(),
                }
            )
            await self._broadcast(event)

            return json.dumps({"status": "ok", "id": notification.id})
        except Exception as e:
            logger.exception("Error handling notify")
            return json.dumps({"status": "error", "message": str(e)})

    def _handle_query(self, msg: dict[str, Any]) -> str:
        """Handle a query action — return matching notifications."""
        status_filter = msg.get("status")
        limit = msg.get("limit", 50)

        if status_filter:
            try:
                status = NotificationStatus(status_filter)
                notifications = self.store.list_by_status(status)
            except ValueError:
                notifications = self.store.list_all(limit=limit)
        else:
            notifications = self.store.list_all(limit=limit)

        return json.dumps(
            {
                "event": "query_result",
                "notifications": [n.to_dict() for n in notifications[:limit]],
            }
        )

    def _handle_update(self, msg: dict[str, Any]) -> str:
        """Handle an update action — change notification status."""
        notification_id = msg.get("id")
        new_status = msg.get("status")

        if not notification_id or not new_status:
            return json.dumps({"status": "error", "message": "Missing id or status"})

        try:
            status = NotificationStatus(new_status)
            self.store.update_status(notification_id, status)
            return json.dumps({"status": "ok"})
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})

    async def _broadcast(self, message: str) -> None:
        """Send a message to all subscribers."""
        dead: list[asyncio.StreamWriter] = []
        for writer in self._subscribers:
            try:
                writer.write((message + "\n").encode())
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                dead.append(writer)
        for w in dead:
            self._subscribers.remove(w)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a connected client."""
        is_subscriber = False
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                raw = data.decode().strip()
                if not raw:
                    continue

                # Check if this is a subscribe request
                try:
                    msg = json.loads(raw)
                    if msg.get("action") == "subscribe":
                        is_subscriber = True
                        self._subscribers.append(writer)
                        writer.write(
                            (json.dumps({"status": "ok", "message": "subscribed"}) + "\n").encode()
                        )
                        await writer.drain()
                        continue
                except json.JSONDecodeError:
                    pass

                response = await self.handle_message(raw)
                writer.write((response + "\n").encode())
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            if is_subscriber and writer in self._subscribers:
                self._subscribers.remove(writer)
            writer.close()

    async def start(self) -> None:
        """Start the daemon server."""
        ensure_config_dirs()

        # Clean up stale socket
        if NOTIFYD_SOCKET.exists():
            NOTIFYD_SOCKET.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(NOTIFYD_SOCKET)
        )

        # Restrict socket to owner only
        os.chmod(str(NOTIFYD_SOCKET), 0o600)

        # Write PID file
        NOTIFYD_PID_FILE.write_text(str(os.getpid()))

        logger.info(f"Notification daemon started on {NOTIFYD_SOCKET}")

        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the daemon server."""
        if self._server:
            self._server.close()
        self.store.close()
        # Clean up files
        if NOTIFYD_SOCKET.exists():
            NOTIFYD_SOCKET.unlink()
        if NOTIFYD_PID_FILE.exists():
            NOTIFYD_PID_FILE.unlink()
        logger.info("Notification daemon stopped")


def is_daemon_running() -> bool:
    """Check if the daemon is running by verifying PID file."""
    if not NOTIFYD_PID_FILE.exists():
        return False
    try:
        pid = int(NOTIFYD_PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Signal 0 = check if process exists
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        # Stale PID file — clean up
        NOTIFYD_PID_FILE.unlink(missing_ok=True)
        return False


def stop_daemon() -> bool:
    """Stop the daemon by sending SIGTERM."""
    if not NOTIFYD_PID_FILE.exists():
        return False
    try:
        pid = int(NOTIFYD_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        NOTIFYD_PID_FILE.unlink(missing_ok=True)
        return False


def run_daemon() -> None:
    """Run the daemon in the foreground (called from CLI)."""
    daemon = NotificationDaemon()

    def _shutdown(sig: int, frame: Any) -> None:
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        daemon.stop()
