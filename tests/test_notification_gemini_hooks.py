"""Tests for Gemini CLI hook handler."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks.gemini import handle_hook_event
from kata.services.notifications.models import NotificationType


class TestHandleGeminiHookEvent:
    """Tests for the Gemini dispatch pipeline."""

    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        # Should not raise — just returns
        handle_hook_event("after-agent", "{}")

    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_invalid_json_returns_early(self, mock_settings):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("after-agent", "not json")

    @patch("kata.services.notifications.hooks.gemini.update_session_state")
    @patch("kata.services.notifications.hooks.gemini.notify")
    @patch("kata.services.notifications.hooks.gemini.generate_summary")
    @patch("kata.services.notifications.hooks.gemini.get_git_branch")
    @patch("kata.services.notifications.hooks.gemini._resolve_session_name")
    @patch("kata.services.notifications.hooks.gemini.load_session_state")
    @patch("kata.services.notifications.hooks.gemini.is_suppressed")
    @patch("kata.services.notifications.hooks.gemini.acquire_lock")
    @patch("kata.services.notifications.hooks.gemini.is_duplicate_early")
    @patch("kata.services.notifications.hooks.gemini.analyze_transcript")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_after_agent_full_pipeline(
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
        mock_resolve.return_value = "gemini-project"
        mock_branch.return_value = "main"
        mock_summary.return_value = "Task finished successfully"

        stdin = json.dumps(
            {
                "session_id": "gem1",
                "transcript_path": "/tmp/gemini_transcript.jsonl",
                "cwd": "/home/user/gemini-project",
                "prompt_response": "I have completed the task.",
            }
        )
        handle_hook_event("after-agent", stdin)

        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["type"] == NotificationType.TASK_COMPLETE
        assert call_kwargs["session_name"] == "gemini-project"
        assert call_kwargs["source"].value == "gemini"
        mock_update_state.assert_called_once_with("gem1", NotificationType.TASK_COMPLETE)

    @patch("kata.services.notifications.hooks.gemini.update_session_state")
    @patch("kata.services.notifications.hooks.gemini.notify")
    @patch("kata.services.notifications.hooks.gemini.acquire_lock")
    @patch("kata.services.notifications.hooks.gemini.is_duplicate_early")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_before_tool_ask_user(
        self,
        mock_settings,
        mock_dedup_early,
        mock_lock,
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
        mock_lock.return_value = True

        stdin = json.dumps(
            {
                "session_id": "gem2",
                "tool_name": "ask_user",
            }
        )
        handle_hook_event("before-tool", stdin)

        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["type"] == NotificationType.QUESTION


class TestGeminiSetupHooks:
    """Tests for setup_hooks function in gemini hook."""

    @patch("kata.services.notifications.hooks.gemini.Path")
    def test_setup_creates_gemini_hooks(self, mock_path_class):
        import json as _json

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "{}"
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path
        mock_path.parent = mock_path

        written_data = {}

        def capture_write(data):
            written_data["content"] = data

        mock_path.write_text = capture_write

        from kata.services.notifications.hooks.gemini import setup_hooks

        setup_hooks()

        parsed = _json.loads(written_data["content"])
        hooks = parsed.get("hooks", {})
        assert "AfterAgent" in hooks
        assert "BeforeTool" in hooks
        assert "Notification" in hooks
        assert "SessionEnd" in hooks

        # Check command
        after_agent = hooks["AfterAgent"][0]["hooks"][0]["command"]
        assert "kata notify-hook after-agent" in after_agent
