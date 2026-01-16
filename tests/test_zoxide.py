"""Tests for zoxide utilities."""

from unittest.mock import MagicMock, patch

import pytest

from kata.utils.zoxide import ZoxideEntry, is_zoxide_available, query_zoxide


class TestZoxideEntry:
    """Tests for ZoxideEntry dataclass."""

    def test_creates_entry_with_all_fields(self):
        """Test creates entry with path, score, and name."""
        entry = ZoxideEntry(path="/home/user/project", score=100.5, name="project")

        assert entry.path == "/home/user/project"
        assert entry.score == 100.5
        assert entry.name == "project"

    def test_exists_returns_true_for_existing_directory(self, tmp_path):
        """Test exists property returns True for existing directories."""
        entry = ZoxideEntry(path=str(tmp_path), score=10.0, name=tmp_path.name)
        assert entry.exists is True

    def test_exists_returns_false_for_nonexistent_directory(self):
        """Test exists property returns False for nonexistent directories."""
        entry = ZoxideEntry(
            path="/nonexistent/path/that/should/not/exist",
            score=10.0,
            name="notexist",
        )
        assert entry.exists is False


class TestIsZoxideAvailable:
    """Tests for is_zoxide_available function."""

    def test_returns_true_when_zoxide_installed(self):
        """Test returns True when zoxide is in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/zoxide"):
            assert is_zoxide_available() is True

    def test_returns_false_when_zoxide_not_installed(self):
        """Test returns False when zoxide is not in PATH."""
        with patch("shutil.which", return_value=None):
            assert is_zoxide_available() is False


class TestQueryZoxide:
    """Tests for query_zoxide function."""

    def test_returns_empty_list_when_zoxide_not_available(self):
        """Test returns empty list when zoxide is not installed."""
        with patch("kata.utils.zoxide.is_zoxide_available", return_value=False):
            result = query_zoxide()
            assert result == []

    def test_returns_empty_list_on_zoxide_error(self):
        """Test returns empty list when zoxide command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide()
                assert result == []

    def test_parses_zoxide_output_correctly(self, tmp_path):
        """Test parses zoxide query output correctly."""
        # Create a temporary directory that exists
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"100.5 {project_dir}\n50.0 /nonexistent/path\n"

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide()

                # Should only include the existing directory
                assert len(result) == 1
                assert result[0].path == str(project_dir)
                assert result[0].score == 100.5
                assert result[0].name == "myproject"

    def test_respects_limit_parameter(self, tmp_path):
        """Test respects the limit parameter."""
        # Create multiple temporary directories
        dirs = []
        for i in range(5):
            d = tmp_path / f"project{i}"
            d.mkdir()
            dirs.append(d)

        output_lines = "\n".join(f"{100 - i * 10}.0 {d}" for i, d in enumerate(dirs))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = output_lines

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide(limit=3)
                assert len(result) == 3

    def test_excludes_specified_paths(self, tmp_path):
        """Test excludes paths in exclude_paths set."""
        project1 = tmp_path / "project1"
        project2 = tmp_path / "project2"
        project1.mkdir()
        project2.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"100.0 {project1}\n50.0 {project2}\n"

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide(exclude_paths={str(project1)})

                assert len(result) == 1
                assert result[0].path == str(project2)

    def test_excludes_home_directory(self, tmp_path):
        """Test excludes the home directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                with patch("pathlib.Path.home", return_value=tmp_path):
                    mock_result.stdout = f"100.0 {tmp_path}\n50.0 {project_dir}\n"
                    result = query_zoxide()

                    # Should only include project_dir, not home
                    assert len(result) == 1
                    assert result[0].path == str(project_dir)

    def test_handles_empty_output(self):
        """Test handles empty zoxide output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide()
                assert result == []

    def test_handles_malformed_lines(self, tmp_path):
        """Test skips malformed output lines."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"malformed line\n100.0 {project_dir}\nnot a score /path\n"

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result):
                result = query_zoxide()

                assert len(result) == 1
                assert result[0].path == str(project_dir)

    def test_handles_timeout(self):
        """Test handles subprocess timeout gracefully."""
        import subprocess

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("zoxide", 5)):
                result = query_zoxide()
                assert result == []

    def test_handles_file_not_found(self):
        """Test handles FileNotFoundError gracefully."""
        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                result = query_zoxide()
                assert result == []

    def test_calls_zoxide_with_correct_args(self):
        """Test calls zoxide with -l and -s flags."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("kata.utils.zoxide.is_zoxide_available", return_value=True):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                query_zoxide()

                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args == ["zoxide", "query", "-l", "-s"]
