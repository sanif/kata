# tests/test_worktree_cli.py
from unittest.mock import patch

from typer.testing import CliRunner

from kata.cli.app import app

runner = CliRunner()


class TestWorktreeStripCommand:
    @patch("kata.cli.worktree_strip.run_worktree_strip")
    def test_popup_flag_runs_strip(self, mock_run):
        result = runner.invoke(app, ["worktree-strip", "--popup"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    @patch("kata.cli.worktree_strip.open_worktree_popup")
    def test_no_flag_opens_popup(self, mock_open):
        result = runner.invoke(app, ["worktree-strip"])
        assert result.exit_code == 0
        mock_open.assert_called_once()
