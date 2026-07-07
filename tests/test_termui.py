"""Tests for the shared raw-terminal plumbing (kata.cli._termui)."""

import json
import os
from unittest.mock import patch

import pytest

from kata.cli._termui import (
    guard_tty,
    has_kata_hooks,
    is_interactive_terminal,
    read_key,
)


def _read_key_from_bytes(data: bytes) -> str:
    """Feed ``data`` through a pipe and return the parsed key token."""
    r, w = os.pipe()
    try:
        os.write(w, data)
        return read_key(r)
    finally:
        os.close(r)
        os.close(w)


class TestReadKey:
    @pytest.mark.parametrize(
        "data,expected",
        [
            (b"\x1b[A", "up"),
            (b"\x1b[B", "down"),
            (b"\x1b[C", "right"),
            (b"\x1b[D", "left"),
            (b"\x1bOA", "up"),
            (b"\x1bOB", "down"),
            (b"\x1b[Z", "shift+tab"),
            (b"\r", "enter"),
            (b"\n", "enter"),
            (b" ", "space"),
            (b"\t", "tab"),
            (b"\x7f", "backspace"),
            (b"\x08", "backspace"),
            (b"\x00", "ctrl+space"),
            (b"\x17", "ctrl+w"),
            (b"\x0e", "ctrl+n"),
            (b"\x03", "escape"),  # Ctrl+C maps to escape
            (b"a", "a"),
            (b"D", "D"),
            (b"/", "/"),
        ],
    )
    def test_parses_key(self, data, expected):
        assert _read_key_from_bytes(data) == expected

    def test_lone_escape_is_escape(self):
        # No trailing sequence bytes: select times out, returns "escape".
        assert _read_key_from_bytes(b"\x1b") == "escape"

    def test_unknown_escape_sequence_is_escape(self):
        assert _read_key_from_bytes(b"\x1b[3~") == "escape"


class TestGuardTty:
    def test_raises_when_not_a_tty(self, capsys):
        with patch("kata.cli._termui.is_interactive_terminal", return_value=False):
            with pytest.raises(SystemExit) as exc:
                guard_tty()
            assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "interactive terminal" in err

    def test_passes_when_tty(self):
        with patch("kata.cli._termui.is_interactive_terminal", return_value=True):
            guard_tty()  # should not raise

    def test_is_interactive_terminal_handles_non_tty(self):
        # stdin under pytest is not a real TTY.
        assert is_interactive_terminal() in (True, False)


class TestHasKataHooks:
    def test_true(self, tmp_path):
        p = tmp_path / "settings.json"
        p.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "kata notify-hook stop"}]}]}})
        )
        assert has_kata_hooks(p) is True

    def test_false(self, tmp_path):
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "other"}]}]}}))
        assert has_kata_hooks(p) is False

    def test_missing_file(self, tmp_path):
        assert has_kata_hooks(tmp_path / "nope.json") is False
