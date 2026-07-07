"""Notification daemon — asyncio Unix socket server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket as _socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from kata.core.config import (
    KATA_CONFIG_DIR,
    NOTIFYD_PID_FILE,
    NOTIFYD_SOCKET,
    ensure_config_dirs,
)
from kata.core.constants import NOTIFY_CONNECT_TIMEOUT, NOTIFYD_PRUNE_INTERVAL_SECONDS
from kata.services.notifications.models import Notification, NotificationStatus
from kata.services.notifications.store import NotificationStore

logger = logging.getLogger(__name__)


class DaemonAlreadyRunning(RuntimeError):
    """Raised when start() detects a live daemon already answering the socket."""


class NotificationDaemon:
    """Background daemon that manages notifications via Unix socket."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the daemon."""
        self.store = NotificationStore(db_path=db_path)
        self._server: asyncio.AbstractServer | None = None
        self._prune_task: asyncio.Task[None] | None = None
        self._owns_files = False

    async def handle_message(self, raw: str) -> str:
        """Handle a single message and return a response."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

        if not isinstance(msg, dict):
            return json.dumps({"status": "error", "message": "Payload must be an object"})

        action = msg.get("action")

        if action == "ping":
            return json.dumps({"status": "pong"})
        elif action == "notify":
            return self._handle_notify(msg)
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

    def _handle_notify(self, msg: dict[str, Any]) -> str:
        """Handle a notify action — validate and store."""
        try:
            notification_data = msg.get("notification")
            if not isinstance(notification_data, dict):
                return json.dumps(
                    {"status": "error", "message": "Missing or invalid 'notification'"}
                )
            notification = Notification.from_dict(notification_data)
            self.store.add(notification)
            return json.dumps({"status": "ok", "id": notification.id})
        except (KeyError, ValueError, TypeError) as e:
            return json.dumps({"status": "error", "message": f"Invalid notification: {e}"})
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Error handling notify")
            return json.dumps({"status": "error", "message": str(e)})

    def _handle_query(self, msg: dict[str, Any]) -> str:
        """Handle a query action — return matching notifications."""
        limit = msg.get("limit", 50)
        if isinstance(limit, bool) or not isinstance(limit, int):
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                return json.dumps({"status": "error", "message": "Invalid 'limit'"})

        status_filter = msg.get("status")
        if status_filter is not None and not isinstance(status_filter, str):
            return json.dumps({"status": "error", "message": "Invalid 'status'"})

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

        if not isinstance(notification_id, str) or not isinstance(new_status, str):
            return json.dumps({"status": "error", "message": "Missing or invalid id/status"})

        try:
            status = NotificationStatus(new_status)
            self.store.update_status(notification_id, status)
            return json.dumps({"status": "ok"})
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a connected client."""
        try:
            while True:
                try:
                    data = await reader.readline()
                except (ValueError, asyncio.LimitOverrunError):
                    # Oversized line (>stream limit). Report and drop the client
                    # rather than letting the exception kill us uncaught.
                    try:
                        writer.write(
                            (
                                json.dumps({"status": "error", "message": "Line too long"}) + "\n"
                            ).encode()
                        )
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    break

                if not data:
                    break
                raw = data.decode(errors="replace").strip()
                if not raw:
                    continue

                response = await self.handle_message(raw)
                writer.write((response + "\n").encode())
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    def _prune_once(self) -> None:
        """Prune the store using current retention settings (best-effort)."""
        try:
            from kata.core.settings import get_settings

            settings = get_settings()
            removed = self.store.prune(
                max_age_days=settings.notifications_retention_days,
                max_count=settings.notifications_max_count,
            )
            if removed:
                logger.debug("Pruned %d notifications", removed)
        except Exception:
            logger.debug("Prune failed", exc_info=True)

    async def _prune_loop(self) -> None:
        """Periodically prune the store so retention works for hook-only users."""
        while True:
            await asyncio.sleep(NOTIFYD_PRUNE_INTERVAL_SECONDS)
            self._prune_once()

    async def start(self) -> None:
        """Start the daemon server."""
        ensure_config_dirs()

        # Refuse to start if a live daemon already answers the socket. Only
        # unlink the socket once we're sure nothing is listening.
        if NOTIFYD_SOCKET.exists():
            if _ping_socket():
                raise DaemonAlreadyRunning("A notification daemon is already running")
            try:
                NOTIFYD_SOCKET.unlink()
            except OSError:
                logger.debug("Failed to unlink stale socket", exc_info=True)

        # Restrict the socket to owner-only from the moment of creation.
        old_umask = os.umask(0o177)
        try:
            self._server = await asyncio.start_unix_server(
                self._handle_client, path=str(NOTIFYD_SOCKET)
            )
        finally:
            os.umask(old_umask)

        # Belt-and-braces: enforce owner-only perms even if umask was ignored.
        try:
            os.chmod(str(NOTIFYD_SOCKET), 0o600)
        except OSError:
            logger.debug("Failed to chmod socket", exc_info=True)

        # Write PID file and take ownership of the files for cleanup.
        NOTIFYD_PID_FILE.write_text(str(os.getpid()))
        self._owns_files = True

        # Prune on startup, then hourly.
        self._prune_once()
        self._prune_task = asyncio.ensure_future(self._prune_loop())

        logger.info(f"Notification daemon started on {NOTIFYD_SOCKET}")

        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the daemon server, cleaning up only files we own."""
        if self._prune_task is not None:
            self._prune_task.cancel()
            self._prune_task = None
        if self._server:
            self._server.close()
        self.store.close()

        # Only remove the socket/PID file if they belong to *this* daemon, so a
        # second (already-running) daemon's files are never stolen.
        if self._owns_files:
            try:
                if NOTIFYD_PID_FILE.exists() and NOTIFYD_PID_FILE.read_text().strip() == str(
                    os.getpid()
                ):
                    NOTIFYD_PID_FILE.unlink(missing_ok=True)
                    NOTIFYD_SOCKET.unlink(missing_ok=True)
            except OSError:
                logger.debug("Failed to clean up daemon files", exc_info=True)
        logger.info("Notification daemon stopped")


def _ping_socket() -> bool:
    """Return True if a live daemon answers a ping on the Unix socket.

    Uses a blocking stdlib socket with a short timeout so it is safe to call
    from synchronous contexts (CLI, start() guard).
    """
    if not NOTIFYD_SOCKET.exists():
        return False
    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(NOTIFY_CONNECT_TIMEOUT)
            s.connect(str(NOTIFYD_SOCKET))
            s.sendall(b'{"action": "ping"}\n')
            data = s.recv(4096)
        return b"pong" in data
    except OSError:
        return False


def is_daemon_running() -> bool:
    """Check if the daemon is running via PID file, cross-checked with the socket."""
    if NOTIFYD_PID_FILE.exists():
        try:
            pid = int(NOTIFYD_PID_FILE.read_text().strip())
            os.kill(pid, 0)  # Signal 0 = check if process exists
            return True
        except ProcessLookupError:
            # Process is gone — clean up the stale PID file.
            NOTIFYD_PID_FILE.unlink(missing_ok=True)
        except PermissionError:
            # Process exists but is owned by another user — do NOT unlink.
            return True
        except ValueError:
            NOTIFYD_PID_FILE.unlink(missing_ok=True)

    # No usable PID file — fall back to asking the socket directly, in case the
    # PID file is missing or stale but a daemon is genuinely listening.
    return _ping_socket()


def stop_daemon() -> bool:
    """Stop the daemon by sending SIGTERM."""
    if not NOTIFYD_PID_FILE.exists():
        return False
    try:
        pid = int(NOTIFYD_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        return True
    except (ValueError, ProcessLookupError):
        NOTIFYD_PID_FILE.unlink(missing_ok=True)
        return False
    except PermissionError:
        # Owned by another user — leave the PID file in place.
        return False


def spawn_detached() -> int:
    """Launch the daemon as a fully detached background process.

    Unlike ``multiprocessing.Process(daemon=True)`` (which the OS kills when the
    parent exits), this uses ``start_new_session=True`` so the daemon survives
    the CLI process exiting. Returns the daemon PID.
    """
    ensure_config_dirs()
    log_path = KATA_CONFIG_DIR / "notifyd.log"

    log_file = None
    try:
        log_file = open(log_path, "a")
        stdout: Any = log_file
        stderr: Any = log_file
    except OSError:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "kata.services.notifications.daemon"],
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        if log_file is not None:
            # The child dup'd the fd; the parent's copy is no longer needed.
            log_file.close()

    return proc.pid


def run_daemon() -> None:
    """Run the daemon in the foreground (entrypoint for ``python -m``)."""
    daemon = NotificationDaemon()

    def _shutdown(sig: int, frame: Any) -> None:
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        asyncio.run(daemon.start())
    except DaemonAlreadyRunning:
        logger.info("Notification daemon already running; exiting")
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    run_daemon()
