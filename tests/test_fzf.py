"""Tests for fzf utilities."""

from unittest.mock import MagicMock, patch

import pytest

from kata.utils.fzf import is_fzf_available, run_fzf_picker


class TestIsFzfAvailable:
    """Tests for is_fzf_available function."""

    def test_returns_true_when_fzf_installed(self):
        """Test returns True when fzf is in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/fzf"):
            assert is_fzf_available() is True

    def test_returns_false_when_fzf_not_installed(self):
        """Test returns False when fzf is not in PATH."""
        with patch("shutil.which", return_value=None):
            assert is_fzf_available() is False


class TestRunFzfPicker:
    """Tests for run_fzf_picker function."""

    def test_raises_when_fzf_not_available(self):
        """Test raises RuntimeError when fzf is not installed."""
        with patch("kata.utils.fzf.is_fzf_available", return_value=False):
            with pytest.raises(RuntimeError, match="fzf is not installed"):
                run_fzf_picker(["item1", "item2"])

    def test_returns_selected_item(self):
        """Test returns the selected item from fzf."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "selected-item\n"

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = run_fzf_picker(["item1", "item2", "selected-item"])

                assert result == "selected-item"
                mock_run.assert_called_once()
                # Verify fzf was called with --ansi flag
                call_args = mock_run.call_args
                assert "--ansi" in call_args[0][0]

    def test_returns_none_on_cancel(self):
        """Test returns None when user cancels (Ctrl-C/Esc)."""
        mock_result = MagicMock()
        mock_result.returncode = 130  # Ctrl-C exit code

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = run_fzf_picker(["item1", "item2"])
                assert result is None

    def test_returns_none_on_no_match(self):
        """Test returns None when no match found."""
        mock_result = MagicMock()
        mock_result.returncode = 1  # No match exit code

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = run_fzf_picker(["item1", "item2"])
                assert result is None

    def test_includes_header_when_provided(self):
        """Test includes --header flag when header is provided."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "item1\n"

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_fzf_picker(["item1"], header="Test Header")

                call_args = mock_run.call_args[0][0]
                assert "--header" in call_args
                header_idx = call_args.index("--header")
                assert call_args[header_idx + 1] == "Test Header"

    def test_includes_preview_when_provided(self):
        """Test includes --preview flag when preview_cmd is provided."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "item1\n"

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_fzf_picker(["item1"], preview_cmd="echo {}")

                call_args = mock_run.call_args[0][0]
                assert "--preview" in call_args
                preview_idx = call_args.index("--preview")
                assert call_args[preview_idx + 1] == "echo {}"

    def test_disables_ansi_when_requested(self):
        """Test does not include --ansi when ansi=False."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "item1\n"

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_fzf_picker(["item1"], ansi=False)

                call_args = mock_run.call_args[0][0]
                assert "--ansi" not in call_args

    def test_passes_items_via_stdin(self):
        """Test items are passed to fzf via stdin."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "item2\n"

        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                run_fzf_picker(["item1", "item2", "item3"])

                call_kwargs = mock_run.call_args[1]
                assert call_kwargs["input"] == "item1\nitem2\nitem3"

    def test_handles_keyboard_interrupt(self):
        """Test handles KeyboardInterrupt gracefully."""
        with patch("kata.utils.fzf.is_fzf_available", return_value=True):
            with patch("subprocess.run", side_effect=KeyboardInterrupt):
                result = run_fzf_picker(["item1", "item2"])
                assert result is None
