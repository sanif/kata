"""Tests for Codex notify hook handler."""

import json
from unittest.mock import MagicMock, patch

from kata.services.notifications.hooks.codex import handle_hook_event, setup_hooks
from kata.services.notifications.models import NotificationSource, NotificationType


class TestHandleCodexHookEvent:
    """The Codex module parses the payload, then delegates to the pipeline."""

    @patch("kata.services.notifications.hooks.codex.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_disabled_notifications_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=False)
        handle_hook_event("{}")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.codex.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_invalid_json_returns_early(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)
        handle_hook_event("not json")
        mock_pipeline.assert_not_called()

    @patch("kata.services.notifications.hooks.codex.run_hook_pipeline")
    @patch("kata.services.notifications.hooks.codex.get_settings")
    def test_delegates_with_task_complete(self, mock_settings, mock_pipeline):
        mock_settings.return_value = MagicMock(notifications_enabled=True)

        payload = json.dumps(
            {
                "type": "agent-turn-complete",
                "thread_id": "t1",
                "cwd": "/home/user/codex-project",
                "last-assistant-message": "Task complete.",
            }
        )
        handle_hook_event(payload)

        mock_pipeline.assert_called_once()
        kwargs = mock_pipeline.call_args.kwargs
        assert kwargs["source"] == NotificationSource.CODEX
        assert kwargs["session_id"] == "t1"
        assert kwargs["last_message"] == "Task complete."
        # Codex classifies directly (no transcript analysis).
        assert kwargs["classify"]() == NotificationType.TASK_COMPLETE
        assert kwargs["extra_metadata"] == {"event_type": "agent-turn-complete"}


class TestCodexSetupHooks:
    """Tests for setup_hooks — notify must land at the top of the file."""

    def _make_path(self, initial_text):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = initial_text
        mock_path.parent = mock_path
        written = {}
        mock_path.write_text = lambda data: written.__setitem__("content", data)
        return mock_path, written

    @patch("kata.services.notifications.hooks.codex.Path")
    def test_creates_notify_line_at_top(self, mock_path_class):
        mock_path, written = self._make_path('model = "gpt-5"\n')
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path

        status = setup_hooks()
        assert status == "installed"
        content = written["content"]
        assert content.startswith('notify = ["kata", "notify-hook", "codex"]')

    @patch("kata.services.notifications.hooks.codex.Path")
    def test_config_ending_in_table_gets_notify_at_top(self, mock_path_class):
        # If we appended at EOF it would land *inside* [model_providers.foo].
        cfg = 'model = "gpt-5"\n\n[model_providers.foo]\nbase_url = "http://x"\n'
        mock_path, written = self._make_path(cfg)
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path

        status = setup_hooks()
        assert status == "installed"
        content = written["content"]
        # notify must be before the table header, not after it.
        assert content.index('notify = ["kata"') < content.index("[model_providers.foo]")

    @patch("kata.services.notifications.hooks.codex.Path")
    def test_user_owned_notify_is_preserved(self, mock_path_class):
        cfg = 'notify = ["my-own-notifier"]\nmodel = "gpt-5"\n'
        mock_path, written = self._make_path(cfg)
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path

        status = setup_hooks()
        assert status == "existing_notify_preserved"
        # Nothing written — the user's config is untouched.
        assert "content" not in written

    @patch("kata.services.notifications.hooks.codex.Path")
    def test_already_installed_is_noop(self, mock_path_class):
        cfg = 'notify = ["kata", "notify-hook", "codex"]\nmodel = "gpt-5"\n'
        mock_path, written = self._make_path(cfg)
        mock_path_class.home.return_value.__truediv__ = lambda self, x: mock_path
        mock_path.__truediv__ = lambda self, x: mock_path

        status = setup_hooks()
        assert status == "already_installed"
        assert "content" not in written
