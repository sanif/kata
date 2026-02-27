"""Tests for rewritten macOS notification dispatcher."""

from unittest.mock import patch

from kata.services.notifications.dispatch.macos import (
    TYPE_EMOJI,
    build_notification_title,
    get_git_branch,
)
from kata.services.notifications.models import NotificationType


class TestGetGitBranch:
    @patch("kata.services.notifications.dispatch.macos.subprocess.run")
    def test_returns_branch_name(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "feature/my-branch\n"
        assert get_git_branch("/some/path") == "feature/my-branch"

    @patch("kata.services.notifications.dispatch.macos.subprocess.run")
    def test_returns_empty_on_error(self, mock_run):
        mock_run.return_value.returncode = 128
        mock_run.return_value.stdout = ""
        assert get_git_branch("/some/path") == ""

    def test_returns_empty_for_no_cwd(self):
        assert get_git_branch("") == ""


class TestBuildTitle:
    def test_title_with_branch(self):
        title = build_notification_title(NotificationType.TASK_COMPLETE, "Task Completed", "main")
        emoji = TYPE_EMOJI[NotificationType.TASK_COMPLETE]
        assert emoji in title
        assert "Task Completed" in title
        assert "[main]" in title

    def test_title_without_branch(self):
        title = build_notification_title(NotificationType.ERROR, "Error", "")
        assert "[" not in title
        assert "Error" in title
