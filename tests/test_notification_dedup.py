"""Tests for single-phase notification deduplication."""

import time

from kata.services.notifications.dispatch import dedup
from kata.services.notifications.dispatch.dedup import check_and_acquire


class TestCheckAndAcquire:
    def test_first_event_acquires(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert check_and_acquire("sess1", "stop") is True
        assert (tmp_path / "kata-dedup-sess1-stop.lock").exists()

    def test_second_recent_event_is_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert check_and_acquire("sess1", "stop") is True
        assert check_and_acquire("sess1", "stop") is False

    def test_different_session_not_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert check_and_acquire("sess1", "stop") is True
        assert check_and_acquire("sess2", "stop") is True

    def test_different_type_not_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert check_and_acquire("sess1", "stop") is True
        assert check_and_acquire("sess1", "notification") is True

    def test_corrupt_lock_treated_as_expired(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        lock = tmp_path / "kata-dedup-sess1-stop.lock"
        lock.write_text("not-a-float")
        # Corrupt lock is treated as expired -> re-acquire and proceed.
        assert check_and_acquire("sess1", "stop") is True

    def test_no_blind_window(self, tmp_path, monkeypatch):
        """The old two-phase design silently dropped events 2-10s after the
        first. Verify a single-phase TTL: dup at t=1s, allowed again at t=3s."""
        monkeypatch.setenv("TMPDIR", str(tmp_path))

        clock = {"now": 1000.0}
        monkeypatch.setattr(dedup.time, "time", lambda: clock["now"])

        # t=0: first event proceeds and records lock@1000.
        assert check_and_acquire("sess1", "stop", ttl=2.0) is True

        # t=1s: within TTL -> duplicate.
        clock["now"] = 1001.0
        assert check_and_acquire("sess1", "stop", ttl=2.0) is False

        # t=3s: older than TTL -> expired, should proceed (this is exactly the
        # 2-10s window the old design blocked).
        clock["now"] = 1003.0
        assert check_and_acquire("sess1", "stop", ttl=2.0) is True

        # Immediately after re-acquire, a fresh duplicate is blocked again.
        clock["now"] = 1003.5
        assert check_and_acquire("sess1", "stop", ttl=2.0) is False


def test_check_and_acquire_survives_realtime(tmp_path, monkeypatch):
    """Smoke test against the real clock (no mocking)."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    assert check_and_acquire("real", "stop", ttl=0.05) is True
    assert check_and_acquire("real", "stop", ttl=0.05) is False
    time.sleep(0.06)
    assert check_and_acquire("real", "stop", ttl=0.05) is True
