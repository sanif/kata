"""Tests for Gemini CLI hook handler."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks.gemini import handle_hook_event
from kata.services.notifications.models import NotificationSource, NotificationType


class TestHandleGeminiHookEvent:
    """The Gemini module parses + classifies, then delegates to the pipeline."""

    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        handle_hook_event("after-agent", "{}")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_invalid_json_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("after-agent", "not json")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_no_session_id_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("after-agent", json.dumps({"cwd": "/x"}))
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.gemini.analyze_transcript")
    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_after_agent_delegates_with_transcript_classifier(
        self, mock_settings, mock_pipeline, mock_analyze
    ):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        mock_analyze.return_value = NotificationType.TASK_COMPLETE

        stdin = json.dumps(
            {
                "session_id": "gem1",
                "transcript_path": "/tmp/gemini_transcript.jsonl",
                "cwd": "/home/user/gemini-project",
                "prompt_response": "I have completed the task.",
            }
        )
        handle_hook_event("after-agent", stdin)

        mock_pipeline.assert_called_once()
        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs["source"] == NotificationSource.GEMINI
        assert kwargs["session_id"] == "gem1"
        assert kwargs["last_message"] == "I have completed the task."
        assert kwargs["classify"]() == NotificationType.TASK_COMPLETE
        mock_analyze.assert_called_once()

    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_before_tool_ask_user(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event(
            "before-tool", json.dumps({"session_id": "gem2", "tool_name": "ask_user"})
        )
        assert mock_pipeline.call_args.kwargs["classify"]() == NotificationType.QUESTION

    @patch("kata.services.notifications.hooks.gemini.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.gemini.get_settings")
    def test_before_tool_irrelevant_skipped(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event(
            "before-tool", json.dumps({"session_id": "gem2", "tool_name": "read_file"})
        )
        mock_pipeline.assert_not_called()


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
