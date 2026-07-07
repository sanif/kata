"""Single-phase lock deduplication for notification hooks.

Addresses Claude Code bug #9602 where hooks fire multiple times.

A single ``check_and_acquire`` call atomically decides whether an event is a
duplicate. A lock file records the timestamp of the last event we let through
for a (session, hook_type) pair:

* If no lock exists, we create it and proceed.
* If a lock exists and is *younger* than ``ttl``, the event is a duplicate.
* If a lock exists but is *older* than ``ttl`` (or is corrupt/unreadable), it is
  treated as expired: we unlink it and re-acquire, then proceed.

This removes the previous two-phase design's blind window, where a lock TTL of
2s combined with a stale-reap threshold of 10s meant a legitimate event 2-10s
after the first passed the "not a duplicate" check but failed lock acquisition
and was silently dropped.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# A second event of the same (session, type) within this window is a duplicate.
DEDUP_TTL_SECONDS = 2.0


def _lock_path(session_id: str, hook_type: str) -> Path:
    # Read TMPDIR from environment directly so tests can redirect via monkeypatch.
    tmpdir = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    safe_session = session_id.replace("/", "_").replace(" ", "_")
    return tmpdir / f"kata-dedup-{safe_session}-{hook_type}.lock"


def _try_create(lock: Path) -> bool:
    """Atomically create the lock file. Returns True if we created it."""
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, str(time.time()).encode())
        finally:
            os.close(fd)
        return True
    except FileExistsError:
        return False


def check_and_acquire(session_id: str, hook_type: str, ttl: float = DEDUP_TTL_SECONDS) -> bool:
    """Atomically decide whether to proceed with a notification.

    Returns True if the caller acquired the lock and should proceed (either the
    first event, or the previous lock was older than ``ttl`` and is treated as
    expired). Returns False if a fresh lock is held (this event is a duplicate).

    On any unexpected OS error we fail open (return True) so notifications are
    never lost to a filesystem hiccup.
    """
    lock = _lock_path(session_id, hook_type)

    try:
        if _try_create(lock):
            return True

        # Lock exists — decide if it is fresh (duplicate) or expired.
        try:
            lock_time = float(lock.read_text().strip())
            age = time.time() - lock_time
        except (ValueError, OSError):
            # Corrupt/unreadable lock — treat as expired.
            age = ttl + 1.0

        if age < ttl:
            logger.debug(f"Dedup: duplicate detected ({age:.1f}s old)")
            return False

        # Expired lock: unlink and re-acquire. A concurrent process may win the
        # re-acquire; if so, this event is the duplicate.
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            logger.debug("Dedup: failed to unlink expired lock", exc_info=True)
        if _try_create(lock):
            return True
        logger.debug("Dedup: lost re-acquire race, treating as duplicate")
        return False
    except OSError:
        logger.debug("Dedup: OS error, failing open", exc_info=True)
        return True
