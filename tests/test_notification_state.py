"""Tests for per-session state manager and suppression."""

from datetime import datetime, timedelta

from kata.services.notifications.dispatch.state import (
    SessionState,
    is_suppressed,
    load_session_state,
    update_session_state,
)
from kata.services.notifications.models import NotificationType


class TestSessionState:
    def test_load_fresh_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        state = load_session_state("new-session")
        assert state.session_id == "new-session"
        assert state.last_notification_type is None

    def test_update_and_reload(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        update_session_state("sess1", NotificationType.TASK_COMPLETE)
        state = load_session_state("sess1")
        assert state.last_notification_type == NotificationType.TASK_COMPLETE
        assert "task_complete" in state.last_by_type


class TestSuppression:
    def test_no_suppression_on_fresh_state(self):
        state = SessionState(session_id="s")
        assert (
            is_suppressed(
                NotificationType.TASK_COMPLETE,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is False
        )

    def test_duplicate_suppressed(self):
        state = SessionState(
            session_id="s",
            last_notification_type=NotificationType.TASK_COMPLETE,
            last_notification_time=datetime.now(),
            last_by_type={"task_complete": datetime.now()},
        )
        assert (
            is_suppressed(
                NotificationType.TASK_COMPLETE,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is True
        )

    def test_duplicate_expired(self):
        state = SessionState(
            session_id="s",
            last_notification_type=NotificationType.TASK_COMPLETE,
            last_notification_time=datetime.now() - timedelta(seconds=10),
            last_by_type={"task_complete": datetime.now() - timedelta(seconds=10)},
        )
        assert (
            is_suppressed(
                NotificationType.TASK_COMPLETE,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is False
        )

    def test_question_after_task_suppressed(self):
        state = SessionState(
            session_id="s",
            last_notification_type=NotificationType.TASK_COMPLETE,
            last_notification_time=datetime.now() - timedelta(seconds=3),
            last_by_type={"task_complete": datetime.now() - timedelta(seconds=3)},
        )
        assert (
            is_suppressed(
                NotificationType.QUESTION,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is True
        )

    def test_question_after_task_expired(self):
        state = SessionState(
            session_id="s",
            last_notification_type=NotificationType.TASK_COMPLETE,
            last_notification_time=datetime.now() - timedelta(seconds=20),
            last_by_type={"task_complete": datetime.now() - timedelta(seconds=20)},
        )
        assert (
            is_suppressed(
                NotificationType.QUESTION,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is False
        )

    def test_question_after_any_suppressed(self):
        state = SessionState(
            session_id="s",
            last_notification_type=NotificationType.ERROR,
            last_notification_time=datetime.now() - timedelta(seconds=5),
            last_by_type={"error": datetime.now() - timedelta(seconds=5)},
        )
        assert (
            is_suppressed(
                NotificationType.QUESTION,
                state,
                suppress_dup=5,
                suppress_q_task=12,
                suppress_q_any=12,
            )
            is True
        )
