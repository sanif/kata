"""Tests for uninstall_tui module."""

import json
from unittest.mock import patch

from kata.cli.uninstall_tui import (
    _has_codex_notify,
    _has_kata_hooks,
    _has_tmux_binding,
    _remove_codex_hooks,
    _remove_kata_hooks_from_json,
    _remove_tmux_lines,
)


class TestDetection:
    """Test detection functions."""

    def test_has_kata_hooks_true(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {"hooks": [{"type": "command", "command": "kata notify-hook stop"}]}
                        ]
                    }
                }
            )
        )
        assert _has_kata_hooks(settings) is True

    def test_has_kata_hooks_false(self, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"hooks": {}}))
        assert _has_kata_hooks(settings) is False

    def test_has_kata_hooks_no_file(self, tmp_path):
        assert _has_kata_hooks(tmp_path / "nope.json") is False

    def test_has_codex_notify_true(self, tmp_path):
        config = tmp_path / "config.toml"
        # Actual format produced by codex setup_hooks
        config.write_text('notify = ["kata", "notify-hook", "codex"]\n')
        assert _has_codex_notify(config) is True

    def test_has_codex_notify_false(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text("model = 'gpt-4'\n")
        assert _has_codex_notify(config) is False

    def test_has_tmux_binding(self, tmp_path):
        tmux_conf = tmp_path / ".tmux.conf"
        tmux_conf.write_text('bind-key -n C-Space run-shell -b "kata switch-strip"\n')
        with patch("kata.cli.uninstall_tui.Path.home", return_value=tmp_path):
            assert _has_tmux_binding("switch-strip") is True
            assert _has_tmux_binding("nonexistent") is False


class TestRemoval:
    """Test removal functions."""

    def test_remove_kata_hooks_from_json(self, tmp_path):
        settings = tmp_path / "settings.json"
        data = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "kata notify-hook stop"}]}],
            },
            "other_key": "keep_this",
        }
        settings.write_text(json.dumps(data))

        result = _remove_kata_hooks_from_json(settings)
        assert result is True

        after = json.loads(settings.read_text())
        assert "other_key" in after
        # hooks should be cleaned up (empty Stop removed)
        assert "hooks" not in after or "Stop" not in after.get("hooks", {})

    def test_remove_kata_hooks_preserves_non_kata(self, tmp_path):
        settings = tmp_path / "settings.json"
        data = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "kata notify-hook stop"}]},
                    {"hooks": [{"type": "command", "command": "other-tool hook"}]},
                ],
            },
        }
        settings.write_text(json.dumps(data))

        _remove_kata_hooks_from_json(settings)

        after = json.loads(settings.read_text())
        stop_hooks = after["hooks"]["Stop"]
        assert len(stop_hooks) == 1
        assert "other-tool" in stop_hooks[0]["hooks"][0]["command"]

    def test_remove_codex_hooks(self, tmp_path):
        config = tmp_path / "config.toml"
        config.write_text(
            'model = "gpt-4"\nnotify = ["kata", "notify-hook", "codex"]\nother = true\n'
        )

        result = _remove_codex_hooks(config)
        assert result is True

        after = config.read_text()
        assert "kata" not in after
        assert "model" in after
        assert "other" in after

    def test_remove_tmux_lines(self, tmp_path):
        tmux_conf = tmp_path / ".tmux.conf"
        tmux_conf.write_text(
            "set -g default-terminal screen-256color\n"
            "# Kata workspace orchestrator\n"
            'bind-key -n C-Space run-shell -b "kata switch-strip"\n'
            'bind-key -n C-n run-shell -b "kata notify-popup"\n'
        )
        with patch("kata.cli.uninstall_tui.Path.home", return_value=tmp_path):
            result = _remove_tmux_lines(["switch-strip", "notify-popup"])
            assert result is True

            after = tmux_conf.read_text()
            assert "switch-strip" not in after
            assert "notify-popup" not in after
            assert "Kata workspace" not in after  # Orphaned marker removed
            assert "screen-256color" in after  # Non-kata lines preserved
