"""Tests for the Claude Code hook handler and the shared hook pipeline."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks import common
from kata.services.notifications.hooks.claude_code import handle_hook_event
from kata.services.notifications.hooks.common import identify_notification_source
from kata.services.notifications.models import NotificationSource, NotificationType


class TestHandleHookEvent:
    """The Claude module parses + classifies, then delegates to the pipeline."""

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        handle_hook_event("stop", '{"session_id": "test"}')
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_invalid_json_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("stop", "not json{{{")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_empty_stdin_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("stop", "")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_no_session_id_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("stop", json.dumps({"cwd": "/x"}))
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_subagent_stop_disabled(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_subagent_stop=False,
        )
        handle_hook_event("subagent-stop", json.dumps({"session_id": "s1"}))
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.analyze_transcript")
    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_stop_delegates_with_transcript_classifier(
        self, mock_settings, mock_pipeline, mock_analyze
    ):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True, notifications_subagent_stop=True
        )
        mock_analyze.return_value = NotificationType.TASK_COMPLETE

        stdin = json.dumps(
            {
                "session_id": "sess1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/home/user/project",
                "last_assistant_message": "I fixed the bug",
            }
        )
        handle_hook_event("stop", stdin)

        mock_pipeline.assert_called_once()
        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs["source"] == NotificationSource.CLAUDE_CODE
        assert kwargs["session_id"] == "sess1"
        assert kwargs["last_message"] == "I fixed the bug"
        # classify() should defer to the transcript analyzer.
        assert kwargs["classify"]() == NotificationType.TASK_COMPLETE
        mock_analyze.assert_called_once()

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_notification_uses_message_field_for_body(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        stdin = json.dumps(
            {
                "session_id": "s1",
                "hook_event_name": "Notification",
                "message": "Claude needs your permission to run Bash",
            }
        )
        handle_hook_event("notification", stdin)

        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs["last_message"] == "Claude needs your permission to run Bash"
        assert kwargs["classify"]() == NotificationType.QUESTION


class TestPreToolUseClassification:
    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_exit_plan_mode_classifies_as_plan_ready(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event(
            "pre-tool-use", json.dumps({"session_id": "s1", "tool_name": "ExitPlanMode"})
        )
        assert mock_pipeline.call_args.kwargs["classify"]() == NotificationType.PLAN_READY

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_ask_user_question_classifies_as_question(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event(
            "pre-tool-use", json.dumps({"session_id": "s1", "tool_name": "AskUserQuestion"})
        )
        assert mock_pipeline.call_args.kwargs["classify"]() == NotificationType.QUESTION

    @patch("kata.services.notifications.hooks.claude_code.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_irrelevant_tool_skipped(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("pre-tool-use", json.dumps({"session_id": "s1", "tool_name": "Read"}))
        mock_pipeline.assert_not_called()


class TestRunHookPipeline:
    """The shared dedup -> suppress -> notify -> state sequence."""

    def _settings(self):
        return MagicMock(
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )

    @patch("kata.services.notifications.hooks.common.update_session_state")
    @patch("kata.services.notifications.hooks.common.notify")
    @patch("kata.services.notifications.hooks.common.resolve_session_name")
    @patch("kata.services.notifications.hooks.common.get_git_branch")
    @patch("kata.services.notifications.hooks.common.generate_summary")
    @patch("kata.services.notifications.hooks.common.is_suppressed")
    @patch("kata.services.notifications.hooks.common.load_session_state")
    @patch("kata.services.notifications.hooks.common.check_and_acquire")
    def test_full_pipeline(
        self,
        mock_dedup,
        mock_load,
        mock_suppressed,
        mock_summary,
        mock_branch,
        mock_resolve,
        mock_notify,
        mock_update,
    ):
        mock_dedup.return_value = True
        mock_suppressed.return_value = False
        mock_summary.return_value = "Fixed"
        mock_branch.return_value = "main"
        mock_resolve.return_value = "proj"

        common.run_hook_pipeline(
            source=NotificationSource.CLAUDE_CODE,
            event_type="stop",
            session_id="s1",
            classify=lambda: NotificationType.TASK_COMPLETE,
            settings=self._settings(),
            cwd="/x",
            transcript_path="/t",
            last_message="did stuff",
        )

        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["type"] == NotificationType.TASK_COMPLETE
        assert mock_notify.call_args.kwargs["session_name"] == "proj"
        mock_update.assert_called_once_with("s1", NotificationType.TASK_COMPLETE)

    @patch("kata.services.notifications.hooks.common.notify")
    @patch("kata.services.notifications.hooks.common.check_and_acquire")
    def test_dedup_blocks_before_classify(self, mock_dedup, mock_notify):
        mock_dedup.return_value = False
        classify = MagicMock()
        common.run_hook_pipeline(
            source=NotificationSource.CLAUDE_CODE,
            event_type="stop",
            session_id="s1",
            classify=classify,
            settings=self._settings(),
        )
        classify.assert_not_called()
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.common.update_session_state")
    @patch("kata.services.notifications.hooks.common.notify")
    @patch("kata.services.notifications.hooks.common.is_suppressed")
    @patch("kata.services.notifications.hooks.common.load_session_state")
    @patch("kata.services.notifications.hooks.common.check_and_acquire")
    def test_suppression_blocks(
        self, mock_dedup, mock_load, mock_suppressed, mock_notify, mock_update
    ):
        mock_dedup.return_value = True
        mock_suppressed.return_value = True
        common.run_hook_pipeline(
            source=NotificationSource.CLAUDE_CODE,
            event_type="stop",
            session_id="s1",
            classify=lambda: NotificationType.QUESTION,
            settings=self._settings(),
        )
        mock_notify.assert_not_called()
        mock_update.assert_not_called()


class TestIdentifyNotificationSource:
    def test_claude_notification_payload(self):
        data = {
            "hook_event_name": "Notification",
            "session_id": "abc",
            "transcript_path": "/tmp/t.jsonl",
            "cwd": "/proj",
            "message": "permission needed",
        }
        assert identify_notification_source(data) == NotificationSource.CLAUDE_CODE

    def test_claude_stop_payload(self):
        data = {"hook_event_name": "Stop", "session_id": "abc", "transcript_path": "/t"}
        assert identify_notification_source(data) == NotificationSource.CLAUDE_CODE

    def test_gemini_notification_payload(self):
        data = {"session_id": "g1", "cwd": "/proj", "prompt_response": "All done."}
        assert identify_notification_source(data) == NotificationSource.GEMINI

    def test_gemini_notification_without_hook_event_name(self):
        data = {"session_id": "g1", "message": "attention", "prompt_response": ""}
        assert identify_notification_source(data) == NotificationSource.GEMINI

    def test_codex_payload(self):
        data = {"type": "agent-turn-complete", "thread_id": "t1"}
        assert identify_notification_source(data) == NotificationSource.CODEX

    def test_unknown_defaults_to_claude(self):
        assert identify_notification_source({}) == NotificationSource.CLAUDE_CODE
        assert identify_notification_source({"foo": "bar"}) == NotificationSource.CLAUDE_CODE


class TestSetupHooks:
    """Tests for setup_hooks function."""

    @patch("kata.services.notifications.hooks.claude_code.Path")
    def test_setup_creates_all_hook_types(self, mock_path_class):
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

        from kata.services.notifications.hooks.claude_code import setup_hooks

        setup_hooks()

        parsed = _json.loads(written_data["content"])
        hooks = parsed.get("hooks", {})
        assert "Stop" in hooks
        assert "SubagentStop" in hooks
        assert "PreToolUse" in hooks
        assert "Notification" in hooks

    @patch("kata.services.notifications.hooks.claude_code.Path")
    def test_setup_survives_non_dict_hooks(self, mock_path_class):
        # A malformed settings.json where "hooks" isn't a dict must not crash.
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = '{"hooks": "oops"}'
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path
        mock_path.parent = mock_path
        mock_path.write_text = MagicMock()

        from kata.services.notifications.hooks.claude_code import setup_hooks

        setup_hooks()  # must not raise
        mock_path.write_text.assert_called_once()
