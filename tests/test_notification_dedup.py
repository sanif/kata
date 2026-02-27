"""Tests for two-phase notification deduplication."""

import time

from kata.services.notifications.dispatch.dedup import (
    acquire_lock,
    is_duplicate_early,
)


class TestDedupPhase1:
    def test_no_lock_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert is_duplicate_early("sess1", "stop") is False

    def test_recent_lock_is_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        lock = tmp_path / "kata-dedup-sess1-stop.lock"
        lock.write_text(str(time.time()))
        assert is_duplicate_early("sess1", "stop") is True

    def test_stale_lock_not_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        lock = tmp_path / "kata-dedup-sess1-stop.lock"
        lock.write_text(str(time.time() - 10))
        assert is_duplicate_early("sess1", "stop") is False

    def test_different_session_not_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        lock = tmp_path / "kata-dedup-sess1-stop.lock"
        lock.write_text(str(time.time()))
        assert is_duplicate_early("sess2", "stop") is False


class TestDedupPhase2:
    def test_acquire_lock_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        assert acquire_lock("sess1", "stop") is True
        assert (tmp_path / "kata-dedup-sess1-stop.lock").exists()

    def test_acquire_lock_fails_if_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        lock = tmp_path / "kata-dedup-sess1-stop.lock"
        lock.write_text(str(time.time()))
        assert acquire_lock("sess1", "stop") is False
