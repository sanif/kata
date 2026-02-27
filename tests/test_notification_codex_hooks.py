"""Tests for Codex notify hook handler."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks.codex import handle_hook_event
from kata.services.notifications.models import NotificationType


class TestHandleCodexHookEvent:
    """Tests for the Codex dispatch pipeline."""

    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        handle_hook_event("{}")

    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_invalid_json_returns_early(self, mock_settings):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("not json")

    @patch("kata.services.notifications.hooks.codex.update_session_state")
    @patch("kata.services.notifications.hooks.codex.notify")
    @patch("kata.services.notifications.hooks.codex.generate_summary")
    @patch("kata.services.notifications.hooks.codex.get_git_branch")
    @patch("kata.services.notifications.hooks.codex._resolve_session_name")
    @patch("kata.services.notifications.hooks.codex.load_session_state")
    @patch("kata.services.notifications.hooks.codex.is_suppressed")
    @patch("kata.services.notifications.hooks.codex.acquire_lock")
    @patch("kata.services.notifications.hooks.codex.is_duplicate_early")
    @patch("kata.services.notifications.hooks.codex.analyze_transcript")
    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_full_pipeline(
        self,
        mock_settings,
        mock_analyze,
        mock_dedup_early,
        mock_lock,
        mock_suppressed,
        mock_load_state,
        mock_resolve,
        mock_branch,
        mock_summary,
        mock_notify,
        mock_update_state,
    ):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )
        mock_dedup_early.return_value = False
        mock_analyze.return_value = NotificationType.TASK_COMPLETE
        mock_lock.return_value = True
        mock_suppressed.return_value = False
        mock_load_state.return_value = MagicMock()
        mock_resolve.return_value = "codex-project"
        mock_branch.return_value = "main"
        mock_summary.return_value = "Done"

        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "thread_id": "t1",
                "transcript_path": "/tmp/codex_transcript.jsonl",
                "cwd": "/home/user/codex-project",
                "last-assistant-message": "Task complete.",
            }
        )
        handle_hook_event(payload)

        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["type"] == NotificationType.TASK_COMPLETE
        assert call_kwargs["session_name"] == "codex-project"
        assert call_kwargs["source"].value == "codex"
        mock_update_state.assert_called_once_with("t1", NotificationType.TASK_COMPLETE)


class TestCodexSetupHooks:
    """Tests for setup_hooks function in codex hook."""

    @patch("kata.services.notifications.hooks.codex.Path")
    def test_setup_creates_notify_line(self, mock_path_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = 'model = "gpt-5"\n'
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path
        mock_path.parent = mock_path

        written_data = {}

        def capture_write(data):
            written_data["content"] = data

        mock_path.write_text = capture_write

        from kata.services.notifications.hooks.codex import setup_hooks

        setup_hooks()

        content = written_data["content"]
        assert 'notify = ["kata", "notify-hook", "codex"]' in content
