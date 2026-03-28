"""Per-session state tracking and suppression logic."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kata.services.notifications.models import NotificationType

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Ephemeral per-session notification state."""

    session_id: str
    last_notification_type: NotificationType | None = None
    last_notification_time: datetime | None = None
    last_by_type: dict[str, datetime] = field(default_factory=dict)


def _state_path(session_id: str) -> Path:
    safe = session_id.replace("/", "_").replace(" ", "_")
    tmpdir = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    return tmpdir / f"kata-state-{safe}.json"


def load_session_state(session_id: str) -> SessionState:
    """Load session state from temp file. Returns fresh state if not found."""
    path = _state_path(session_id)
    if not path.exists():
        return SessionState(session_id=session_id)

    try:
        data = json.loads(path.read_text())
        last_type_str = data.get("last_notification_type")
        last_time_str = data.get("last_notification_time")
        last_by_type_raw = data.get("last_by_type", {})

        return SessionState(
            session_id=session_id,
            last_notification_type=NotificationType(last_type_str) if last_type_str else None,
            last_notification_time=datetime.fromisoformat(last_time_str) if last_time_str else None,
            last_by_type={k: datetime.fromisoformat(v) for k, v in last_by_type_raw.items()},
        )
    except Exception:
        logger.debug("Failed to load session state", exc_info=True)
        return SessionState(session_id=session_id)


def update_session_state(session_id: str, notification_type: NotificationType) -> None:
    """Update session state after sending a notification."""
    state = load_session_state(session_id)
    now = datetime.now()

    state.last_notification_type = notification_type
    state.last_notification_time = now
    state.last_by_type[notification_type.value] = now

    path = _state_path(session_id)
    data = {
        "session_id": session_id,
        "last_notification_type": notification_type.value,
        "last_notification_time": now.isoformat(),
        "last_by_type": {k: v.isoformat() for k, v in state.last_by_type.items()},
    }
    temp_file = path.with_suffix(".tmp")
    try:
        temp_file.write_text(json.dumps(data))
        temp_file.rename(path)
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        logger.debug("Failed to save session state", exc_info=True)


def is_suppressed(
    notification_type: NotificationType,
    state: SessionState,
    *,
    suppress_dup: int = 5,
    suppress_q_task: int = 12,
    suppress_q_any: int = 12,
) -> bool:
    """Check if a notification should be suppressed based on cooldown rules.

    Rules:
    1. Same type within suppress_dup seconds -> skip
    2. QUESTION within suppress_q_task seconds of TASK_COMPLETE -> skip
    3. QUESTION within suppress_q_any seconds of any notification -> skip
    """
    now = datetime.now()

    type_key = notification_type.value
    if type_key in state.last_by_type:
        elapsed = (now - state.last_by_type[type_key]).total_seconds()
        if elapsed < suppress_dup:
            logger.debug(f"Suppressed: duplicate {type_key} ({elapsed:.1f}s ago)")
            return True

    if notification_type == NotificationType.QUESTION:
        task_key = NotificationType.TASK_COMPLETE.value
        if task_key in state.last_by_type:
            elapsed = (now - state.last_by_type[task_key]).total_seconds()
            if elapsed < suppress_q_task:
                logger.debug(f"Suppressed: question after task_complete ({elapsed:.1f}s ago)")
                return True

        if state.last_notification_time:
            elapsed = (now - state.last_notification_time).total_seconds()
            if elapsed < suppress_q_any:
                logger.debug(f"Suppressed: question after any notification ({elapsed:.1f}s ago)")
                return True

    return False
