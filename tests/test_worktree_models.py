"""Tests for WorktreeInfo and WorktreeStatus data models."""

from datetime import datetime

from kata.core.models import WorktreeInfo, WorktreeStatus


class TestWorktreeInfo:
    def test_create_worktree_info(self):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        assert wt.name == "fix-auth"
        assert wt.source_session_id is None

    def test_to_dict_roundtrip(self):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fork",
            source_session_id="abc-123",
        )
        d = wt.to_dict()
        wt2 = WorktreeInfo.from_dict(d)
        assert wt2.name == wt.name
        assert wt2.source_session_id == "abc-123"
        assert wt2.context_mode == "fork"


class TestWorktreeStatus:
    def test_create_status(self):
        info = WorktreeInfo(
            name="main",
            branch="main",
            path=".",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        status = WorktreeStatus(
            info=info,
            is_main=True,
            dirty=False,
            changed_files=0,
            session_summary=None,
            session_active=False,
        )
        assert status.is_main is True
        assert status.dirty is False
