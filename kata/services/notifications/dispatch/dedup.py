"""Two-phase lock deduplication for notification hooks.

Addresses Claude Code bug #9602 where hooks fire multiple times.
Phase 1: Fast early exit if recent lock exists (before analysis).
Phase 2: Atomic lock creation after classification (before dispatch).
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_TTL_SECONDS = 2.0
_LOCK_STALE_SECONDS = 10.0


def _lock_path(session_id: str, hook_type: str) -> Path:
    # Read TMPDIR from environment directly so tests can redirect via monkeypatch.
    tmpdir = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    safe_session = session_id.replace("/", "_").replace(" ", "_")
    return tmpdir / f"kata-dedup-{safe_session}-{hook_type}.lock"


def is_duplicate_early(session_id: str, hook_type: str) -> bool:
    """Phase 1: Check if a recent lock exists (fast early exit)."""
    lock = _lock_path(session_id, hook_type)
    if not lock.exists():
        return False

    try:
        lock_time = float(lock.read_text().strip())
        age = time.time() - lock_time
        if age < _LOCK_TTL_SECONDS:
            logger.debug(f"Dedup phase 1: duplicate detected ({age:.1f}s old)")
            return True
        if age > _LOCK_STALE_SECONDS:
            lock.unlink(missing_ok=True)
    except (ValueError, OSError):
        lock.unlink(missing_ok=True)

    return False


def acquire_lock(session_id: str, hook_type: str) -> bool:
    """Phase 2: Atomically create lock file.
    Returns True if lock was acquired (we should proceed).
    Returns False if another process already holds the lock.
    """
    lock = _lock_path(session_id, hook_type)

    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(time.time()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        logger.debug("Dedup phase 2: lock already held")
        return False
    except OSError:
        logger.debug("Dedup phase 2: OS error creating lock", exc_info=True)
        return True
