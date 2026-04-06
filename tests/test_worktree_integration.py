"""Integration tests for worktree feature end-to-end flow."""

from unittest.mock import patch

import pytest

from kata.services.worktrees import (
    WorktreeError,
    _load_metadata,
    create_worktree,
    delete_worktree,
    list_worktrees,
)


def _ok_result(stdout="", stderr=""):
    """Create a successful subprocess result mock."""
    return type("R", (), {"returncode": 0, "stdout": stdout, "stderr": stderr})()


def _git_status_clean():
    """Create a clean GitStatus mock."""
    return type("S", (), {"is_dirty": False, "has_changes": False, "is_git_repo": True})()


class TestWorktreeLifecycle:
    @patch("kata.services.worktrees._run_git")
    @patch("kata.services.worktrees.get_branch_name", return_value="main")
    @patch("kata.services.worktrees.get_git_status")
    def test_full_lifecycle(self, mock_status, mock_branch, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        mock_status.return_value = _git_status_clean()

        # Create
        wt = create_worktree(tmp_path, "feature-x", context_mode="fresh")
        assert wt.name == "feature-x"
        assert wt.branch == "feature-x"
        assert wt.context_mode == "fresh"

        # Verify metadata persisted
        metadata = _load_metadata(tmp_path)
        assert len(metadata) == 1
        assert metadata[0].name == "feature-x"

        # Simulate git creating the worktree directory (normally done by git)
        (tmp_path / ".worktrees" / "feature-x").mkdir(parents=True, exist_ok=True)

        # List — includes main + feature-x
        result = list_worktrees(tmp_path)
        assert len(result) == 2
        assert result[0].is_main
        assert result[1].info.name == "feature-x"

        # Delete
        delete_worktree(tmp_path, "feature-x")
        result2 = list_worktrees(tmp_path)
        assert len(result2) == 1
        assert result2[0].is_main

    @patch("kata.services.worktrees._run_git")
    def test_create_duplicate_raises(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()

        create_worktree(tmp_path, "dup-wt")
        with pytest.raises(WorktreeError, match="already exists"):
            create_worktree(tmp_path, "dup-wt")

    @patch("kata.services.worktrees._run_git")
    def test_delete_main_raises(self, mock_git, tmp_path):
        with pytest.raises(WorktreeError, match="Cannot delete main"):
            delete_worktree(tmp_path, "main")

    @patch("kata.services.worktrees._run_git")
    def test_delete_nonexistent_raises(self, mock_git, tmp_path):
        with pytest.raises(WorktreeError, match="not found"):
            delete_worktree(tmp_path, "ghost")


class TestWorktreeSessionNames:
    def test_session_name_for_main(self):
        from kata.cli.worktree_strip import _get_worktree_session_name

        assert _get_worktree_session_name("cli-pm", "main") == "cli-pm"

    def test_session_name_for_branch(self):
        from kata.cli.worktree_strip import _get_worktree_session_name

        name = _get_worktree_session_name("cli-pm", "fix-auth")
        # Colon is sanitized to underscore
        assert name == "cli-pm_fix-auth"
        assert "cli-pm" in name
        assert "fix-auth" in name

    def test_session_name_sanitizes_dots(self):
        from kata.cli.worktree_strip import _get_worktree_session_name

        name = _get_worktree_session_name("my.project", "v2.0")
        assert "." not in name
        assert ":" not in name


class TestGitignoreManagement:
    @patch("kata.services.worktrees._run_git")
    def test_creates_gitignore_entry(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        create_worktree(tmp_path, "test-wt")
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".worktrees/" in gitignore.read_text()

    @patch("kata.services.worktrees._run_git")
    def test_does_not_duplicate_gitignore_entry(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        (tmp_path / ".gitignore").write_text(".worktrees/\n")
        create_worktree(tmp_path, "test-wt")
        content = (tmp_path / ".gitignore").read_text()
        assert content.count(".worktrees/") == 1

    @patch("kata.services.worktrees._run_git")
    def test_appends_to_existing_gitignore(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        create_worktree(tmp_path, "test-wt")
        content = (tmp_path / ".gitignore").read_text()
        assert "node_modules/" in content
        assert ".worktrees/" in content


class TestContextModes:
    @patch("kata.services.worktrees._run_git")
    def test_create_with_fork_mode(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        wt = create_worktree(tmp_path, "forked", context_mode="fork", source_session_id="abc-123")
        assert wt.context_mode == "fork"
        assert wt.source_session_id == "abc-123"

        # Verify persisted in metadata
        metadata = _load_metadata(tmp_path)
        assert metadata[0].context_mode == "fork"
        assert metadata[0].source_session_id == "abc-123"

    @patch("kata.services.worktrees._run_git")
    def test_create_with_summary_mode(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        wt = create_worktree(tmp_path, "summary-wt", context_mode="summary")
        assert wt.context_mode == "summary"
        assert wt.source_session_id is None

    @patch("kata.services.worktrees._run_git")
    def test_default_context_mode_is_fresh(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        wt = create_worktree(tmp_path, "default-wt")
        assert wt.context_mode == "fresh"


class TestMetadataPersistence:
    @patch("kata.services.worktrees._run_git")
    def test_metadata_survives_multiple_creates(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        create_worktree(tmp_path, "wt-a")
        create_worktree(tmp_path, "wt-b")
        create_worktree(tmp_path, "wt-c")

        metadata = _load_metadata(tmp_path)
        assert len(metadata) == 3
        names = {w.name for w in metadata}
        assert names == {"wt-a", "wt-b", "wt-c"}

    @patch("kata.services.worktrees._run_git")
    def test_metadata_updated_after_delete(self, mock_git, tmp_path):
        mock_git.return_value = _ok_result()
        create_worktree(tmp_path, "keep")
        create_worktree(tmp_path, "remove")

        delete_worktree(tmp_path, "remove")
        metadata = _load_metadata(tmp_path)
        assert len(metadata) == 1
        assert metadata[0].name == "keep"

    def test_load_metadata_empty_project(self, tmp_path):
        metadata = _load_metadata(tmp_path)
        assert metadata == []

    def test_load_metadata_corrupt_json(self, tmp_path):
        meta_path = tmp_path / ".worktrees" / ".kata-worktrees.json"
        meta_path.parent.mkdir(parents=True)
        meta_path.write_text("not json{{{")
        metadata = _load_metadata(tmp_path)
        assert metadata == []
