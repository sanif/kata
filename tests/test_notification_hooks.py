"""Tests for rewritten Claude Code hook handler."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks.claude_code import handle_hook_event
from kata.services.notifications.models import NotificationType


class TestHandleHookEvent:
    """Tests for the main dispatch pipeline."""

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings, mock_notify):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        handle_hook_event("stop", '{"session_id": "test"}')
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_invalid_json_returns_early(self, mock_settings, mock_notify):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("stop", "not json{{{")
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_empty_stdin_returns_early(self, mock_settings, mock_notify):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("stop", "")
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_subagent_stop_disabled(self, mock_settings, mock_notify):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_subagent_stop=False,
        )
        handle_hook_event("subagent-stop", json.dumps({"session_id": "s1"}))
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.update_session_state")
    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.generate_summary")
    @patch("kata.services.notifications.hooks.claude_code.get_git_branch")
    @patch("kata.services.notifications.hooks.claude_code.resolve_session_name")
    @patch("kata.services.notifications.hooks.claude_code.load_session_state")
    @patch("kata.services.notifications.hooks.claude_code.is_suppressed")
    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.analyze_transcript")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_stop_full_pipeline(
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
            notifications_subagent_stop=True,
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )
        mock_dedup_early.return_value = False
        mock_analyze.return_value = NotificationType.TASK_COMPLETE
        mock_lock.return_value = True
        mock_suppressed.return_value = False
        mock_load_state.return_value = MagicMock()
        mock_resolve.return_value = "my-project"
        mock_branch.return_value = "main"
        mock_summary.return_value = "Fixed the bug"

        stdin = json.dumps(
            {
                "session_id": "sess1",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": "/home/user/project",
                "last_assistant_message": "I fixed the bug",
            }
        )
        handle_hook_event("stop", stdin)

        mock_analyze.assert_called_once()
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args
        assert call_kwargs.kwargs["type"] == NotificationType.TASK_COMPLETE
        assert call_kwargs.kwargs["session_name"] == "my-project"
        mock_update_state.assert_called_once_with("sess1", NotificationType.TASK_COMPLETE)

    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_dedup_early_blocks(self, mock_settings, mock_dedup_early, mock_lock):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_subagent_stop=True,
        )
        mock_dedup_early.return_value = True

        handle_hook_event("stop", json.dumps({"session_id": "s1"}))
        mock_lock.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.is_suppressed")
    @patch("kata.services.notifications.hooks.claude_code.load_session_state")
    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_lock_failure_blocks(
        self,
        mock_settings,
        mock_dedup_early,
        mock_lock,
        mock_load_state,
        mock_suppressed,
        mock_notify,
    ):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_subagent_stop=True,
        )
        mock_dedup_early.return_value = False
        mock_lock.return_value = False

        handle_hook_event(
            "stop",
            json.dumps(
                {
                    "session_id": "s1",
                    "transcript_path": "/tmp/t.jsonl",
                }
            ),
        )
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.is_suppressed")
    @patch("kata.services.notifications.hooks.claude_code.load_session_state")
    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.analyze_transcript")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_suppression_blocks(
        self,
        mock_settings,
        mock_analyze,
        mock_dedup_early,
        mock_lock,
        mock_load_state,
        mock_suppressed,
        mock_notify,
    ):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
            notifications_subagent_stop=True,
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )
        mock_dedup_early.return_value = False
        mock_analyze.return_value = NotificationType.TASK_COMPLETE
        mock_lock.return_value = True
        mock_load_state.return_value = MagicMock()
        mock_suppressed.return_value = True

        handle_hook_event(
            "stop",
            json.dumps(
                {
                    "session_id": "s1",
                    "transcript_path": "/tmp/t.jsonl",
                }
            ),
        )
        mock_notify.assert_not_called()


class TestPreToolUseClassification:
    """Tests for pre-tool-use event classification."""

    @patch("kata.services.notifications.hooks.claude_code.update_session_state")
    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.generate_summary")
    @patch("kata.services.notifications.hooks.claude_code.get_git_branch")
    @patch("kata.services.notifications.hooks.claude_code.resolve_session_name")
    @patch("kata.services.notifications.hooks.claude_code.load_session_state")
    @patch("kata.services.notifications.hooks.claude_code.is_suppressed")
    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_exit_plan_mode_classifies_as_plan_ready(
        self,
        mock_settings,
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
            notifications_subagent_stop=True,
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )
        mock_dedup_early.return_value = False
        mock_lock.return_value = True
        mock_suppressed.return_value = False
        mock_load_state.return_value = MagicMock()
        mock_resolve.return_value = "proj"
        mock_branch.return_value = ""
        mock_summary.return_value = ""

        stdin = json.dumps(
            {
                "session_id": "s1",
                "tool_name": "ExitPlanMode",
            }
        )
        handle_hook_event("pre-tool-use", stdin)

        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["type"] == NotificationType.PLAN_READY

    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_irrelevant_tool_skipped(self, mock_settings, mock_dedup_early, mock_notify):
        mock_settings.return_value = MagicMock(
            notifications_enabled=True,
        )
        mock_dedup_early.return_value = False

        stdin = json.dumps(
            {
                "session_id": "s1",
                "tool_name": "Read",
            }
        )
        handle_hook_event("pre-tool-use", stdin)
        mock_notify.assert_not_called()

    @patch("kata.services.notifications.hooks.claude_code.update_session_state")
    @patch("kata.services.notifications.hooks.claude_code.notify")
    @patch("kata.services.notifications.hooks.claude_code.generate_summary")
    @patch("kata.services.notifications.hooks.claude_code.get_git_branch")
    @patch("kata.services.notifications.hooks.claude_code.resolve_session_name")
    @patch("kata.services.notifications.hooks.claude_code.load_session_state")
    @patch("kata.services.notifications.hooks.claude_code.is_suppressed")
    @patch("kata.services.notifications.hooks.claude_code.acquire_lock")
    @patch("kata.services.notifications.hooks.claude_code.is_duplicate_early")
    @patch("kata.services.notifications.hooks.claude_code.get_settings")
    def test_ask_user_question_classifies_as_question(
        self,
        mock_settings,
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
            notifications_subagent_stop=True,
            notifications_suppress_duplicate_seconds=5,
            notifications_suppress_question_after_task_seconds=12,
            notifications_suppress_question_after_any_seconds=12,
        )
        mock_dedup_early.return_value = False
        mock_lock.return_value = True
        mock_suppressed.return_value = False
        mock_load_state.return_value = MagicMock()
        mock_resolve.return_value = "proj"
        mock_branch.return_value = ""
        mock_summary.return_value = ""

        stdin = json.dumps(
            {
                "session_id": "s1",
                "tool_name": "AskUserQuestion",
            }
        )
        handle_hook_event("pre-tool-use", stdin)

        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["type"] == NotificationType.QUESTION


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
