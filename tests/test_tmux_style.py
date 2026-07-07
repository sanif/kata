"""Tests for per-project tmux window styling."""

from unittest.mock import call, patch

from kata.services.tmux_style import (
    _set_window_option,
    _unset_window_option,
    _window_targets,
)


class TestWindowTargets:
    def test_enumerates_all_windows(self):
        with patch("kata.services.tmux_style._run_tmux", return_value="0\n1\n2"):
            targets = _window_targets("mysess")
        assert targets == ["mysess:0", "mysess:1", "mysess:2"]

    def test_no_windows_returns_empty(self):
        with patch("kata.services.tmux_style._run_tmux", return_value=None):
            assert _window_targets("mysess") == []


class TestSetWindowOptionAllWindows:
    def test_set_applies_to_every_window(self):
        with patch(
            "kata.services.tmux_style._window_targets",
            return_value=["s:0", "s:1"],
        ):
            with patch("kata.services.tmux_style._run_tmux") as mock_run:
                _set_window_option("s", "pane-border-status", "top")
        mock_run.assert_has_calls(
            [
                call("set-option", "-w", "-t", "s:0", "pane-border-status", "top"),
                call("set-option", "-w", "-t", "s:1", "pane-border-status", "top"),
            ]
        )
        assert mock_run.call_count == 2

    def test_unset_applies_to_every_window(self):
        with patch(
            "kata.services.tmux_style._window_targets",
            return_value=["s:0", "s:1"],
        ):
            with patch("kata.services.tmux_style._run_tmux") as mock_run:
                _unset_window_option("s", "pane-border-status")
        mock_run.assert_has_calls(
            [
                call("set-option", "-w", "-t", "s:0", "-u", "pane-border-status"),
                call("set-option", "-w", "-t", "s:1", "-u", "pane-border-status"),
            ]
        )
        assert mock_run.call_count == 2
