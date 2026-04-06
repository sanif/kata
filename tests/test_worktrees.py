from datetime import datetime
from unittest.mock import patch

import pytest

from kata.core.models import WorktreeInfo
from kata.services.worktrees import (
    WorktreeError,
    _load_metadata,
    _save_metadata,
    create_worktree,
    delete_worktree,
    list_worktrees,
)


class TestMetadataPersistence:
    def test_save_and_load(self, tmp_path):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])
        loaded = _load_metadata(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].name == "fix-auth"

    def test_load_empty(self, tmp_path):
        loaded = _load_metadata(tmp_path)
        assert loaded == []


class TestCreateWorktree:
    @patch("kata.services.worktrees._run_git")
    def test_create_worktree_success(self, mock_git, tmp_path):
        mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        wt_dir = tmp_path / ".worktrees" / "fix-auth"
        wt_dir.mkdir(parents=True)
        result = create_worktree(tmp_path, "fix-auth")
        assert result.name == "fix-auth"
        assert result.branch == "fix-auth"
        assert result.context_mode == "fresh"
        loaded = _load_metadata(tmp_path)
        assert len(loaded) == 1

    @patch("kata.services.worktrees._run_git")
    def test_create_with_custom_branch(self, mock_git, tmp_path):
        mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        wt_dir = tmp_path / ".worktrees" / "my-feature"
        wt_dir.mkdir(parents=True)
        result = create_worktree(tmp_path, "my-feature", branch="feature/cool")
        assert result.branch == "feature/cool"

    @patch("kata.services.worktrees._run_git")
    def test_create_duplicate_raises(self, mock_git, tmp_path):
        mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        (tmp_path / ".worktrees" / "dup").mkdir(parents=True)
        create_worktree(tmp_path, "dup")
        with pytest.raises(WorktreeError, match="already exists"):
            create_worktree(tmp_path, "dup")


class TestDeleteWorktree:
    @patch("kata.services.worktrees._run_git")
    def test_delete_removes_metadata(self, mock_git, tmp_path):
        mock_git.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])
        delete_worktree(tmp_path, "fix-auth")
        loaded = _load_metadata(tmp_path)
        assert len(loaded) == 0

    def test_delete_main_raises(self, tmp_path):
        with pytest.raises(WorktreeError, match="Cannot delete main"):
            delete_worktree(tmp_path, "main")


class TestListWorktrees:
    def test_list_includes_main(self, tmp_path):
        with patch("kata.services.worktrees.get_branch_name", return_value="main"):
            with patch("kata.services.worktrees.get_git_status") as mock_status:
                mock_status.return_value = type(
                    "S", (), {"is_dirty": False, "has_changes": False}
                )()
                result = list_worktrees(tmp_path)
        assert len(result) == 1
        assert result[0].is_main is True

    def test_list_includes_worktrees_from_metadata(self, tmp_path):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])
        wt_dir = tmp_path / ".worktrees" / "fix-auth"
        wt_dir.mkdir(parents=True)
        with patch("kata.services.worktrees.get_branch_name", return_value="main"):
            with patch("kata.services.worktrees.get_git_status") as mock_status:
                mock_status.return_value = type(
                    "S", (), {"is_dirty": False, "has_changes": False}
                )()
                result = list_worktrees(tmp_path)
        assert len(result) == 2
        assert result[0].is_main is True
        assert result[1].info.name == "fix-auth"
