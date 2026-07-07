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


@pytest.fixture
def mock_git_ok():
    """Patch worktrees._run_git so every git call succeeds."""
    ok = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    with patch("kata.services.worktrees._run_git", return_value=ok):
        yield


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


class TestValidateWorktreeName:
    @pytest.mark.parametrize(
        "bad",
        ["", "   ", "../escape", "a/b", "a\\b", "~home", "-leading", "x" * 101],
    )
    def test_invalid_names_rejected(self, mock_git_ok, tmp_path, bad):
        with pytest.raises(WorktreeError):
            create_worktree(tmp_path, bad)

    def test_valid_name_accepted(self, mock_git_ok, tmp_path):
        (tmp_path / ".worktrees" / "fix-auth").mkdir(parents=True)
        wt = create_worktree(tmp_path, "fix-auth")
        assert wt.name == "fix-auth"


class TestDeleteOrdering:
    """Git removal must happen before kata touches worktree files."""

    def test_git_remove_failure_leaves_metadata_intact(self, tmp_path):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])

        cleanup_calls = []

        def fake_git(args, cwd):
            # worktree remove fails (e.g. locked/submodule)
            if args[:2] == ["worktree", "remove"]:
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "is locked"})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("kata.services.worktrees._run_git", side_effect=fake_git):
            with patch(
                "kata.services.worktrees._cleanup_worktree_files",
                side_effect=lambda p: cleanup_calls.append(p),
            ):
                with patch("kata.services.worktrees._kill_worktree_session"):
                    with pytest.raises(WorktreeError, match="Failed to remove"):
                        delete_worktree(tmp_path, "fix-auth")

        # Cleanup must NOT run when git removal failed, and metadata stays.
        assert cleanup_calls == []
        assert len(_load_metadata(tmp_path)) == 1

    def test_branch_delete_failure_surfaces_warning(self, tmp_path):
        wt = WorktreeInfo(
            name="fix-auth",
            branch="fix-auth",
            path=".worktrees/fix-auth",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])

        def fake_git(args, cwd):
            if args[:2] == ["branch", "-d"] or args[:2] == ["branch", "-D"]:
                return type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "not fully merged"}
                )()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch("kata.services.worktrees._run_git", side_effect=fake_git):
            with patch("kata.services.worktrees._cleanup_worktree_files"):
                with patch("kata.services.worktrees._kill_worktree_session"):
                    warning = delete_worktree(tmp_path, "fix-auth", force=True)

        assert warning is not None
        assert "branch" in warning
        # Worktree itself was removed → metadata cleared.
        assert _load_metadata(tmp_path) == []


class TestMetadataDurability:
    def test_save_metadata_is_atomic_no_fixed_tmp(self, tmp_path):
        wt = WorktreeInfo(
            name="a",
            branch="a",
            path=".worktrees/a",
            created_at=datetime(2026, 4, 6),
            context_mode="fresh",
        )
        _save_metadata(tmp_path, [wt])
        wt_dir = tmp_path / ".worktrees"
        # No leftover fixed-name temp file, and content is valid.
        assert not (wt_dir / ".kata-worktrees.json.tmp").exists()
        assert _load_metadata(tmp_path)[0].name == "a"

    def test_corrupt_metadata_is_backed_up(self, tmp_path):
        path = tmp_path / ".worktrees" / ".kata-worktrees.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"{ not valid json")

        loaded = _load_metadata(path.parent.parent)
        assert loaded == []
        backups = list(path.parent.glob(".kata-worktrees.json.corrupt-*"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == b"{ not valid json"


class TestEnsureGitignore:
    def test_existing_worktrees_entry_not_duplicated(self, mock_git_ok, tmp_path):
        gi = tmp_path / ".gitignore"
        gi.write_text("# comment\n.worktrees/\nnode_modules\n")
        (tmp_path / ".worktrees" / "x").mkdir(parents=True)
        create_worktree(tmp_path, "x")
        # Entry present exactly once.
        assert gi.read_text().count(".worktrees/") == 1

    def test_worktrees_entry_without_slash_matches(self, mock_git_ok, tmp_path):
        gi = tmp_path / ".gitignore"
        gi.write_text(".worktrees\n")
        (tmp_path / ".worktrees" / "x").mkdir(parents=True)
        create_worktree(tmp_path, "x")
        # ".worktrees" (no slash) already covers it; not re-added.
        assert ".worktrees/" not in gi.read_text()
